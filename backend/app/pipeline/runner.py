"""Orchestrates a scan: plan → search (+ probes) → fetch → extract → match → score, streaming progress."""
from __future__ import annotations

import asyncio
import itertools
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from .. import probes
from ..config import Settings
from ..guardrails import mask, redact
from ..models import Finding, ScanFields, SourceStatus
from ..session import Session
from ..tinyfish import CircuitOpen, Hit, TinyFishClient, TinyFishError
from .extract import extract
from .match import confidence_label, page_match, value_matches_input
from .plan import build_queries
from .score import LABELS, playbook_for, rescore, summarise

log = logging.getLogger("fingerprint.scan")

MIN_PAGE_CONFIDENCE_FOR_DETAILS = 0.3
MAX_FINDINGS = 80
MAX_MENTIONS = 20
IDENTIFYING = {"full name", "other name", "name (split)", "email", "username", "phone"}
PRESENCE = {   # domain group → (finding type, category, sensitivity) for "this page is about you"
    "broker": ("listing", "broker", "high"),
    "social": ("profile", "social", "medium"),
    "professional": ("profile", "work", "medium"),
    "code": ("profile", "code", "low"),
    "documents": ("document", "identity", "medium"),
    "news": ("mention", "identity", "low"),
}


@dataclass
class Candidate:
    hit: Hit
    domain: str
    group: str | None
    confidence: float
    reasons: list[str]
    purposes: set[str] = field(default_factory=set)


class Scan:
    def __init__(self, session: Session, settings: Settings, tf: TinyFishClient, http: httpx.AsyncClient):
        self.s = session
        self.cfg = settings
        self.tf = tf
        self.http = http
        self.f: ScanFields = session.request.fields
        self.level = session.request.level
        self.findings: list[Finding] = []
        self._ids = itertools.count(1)
        self._keys: set[tuple[str, str, str]] = set()
        self.partial = False
        self.cost = 0.0
        self.agent_runs = 0
        self._mentions = 0

    # ── events ──────────────────────────────────────────────────────────────
    def stage(self, stage: str, label: str) -> None:
        self.s.emit({"type": "stage", "stage": stage, "label": label})

    def source(self, name: str, kind: str, status: str, detail: str = "") -> None:
        name = redact(name)                               # page URLs can contain phone numbers
        self.s.emit({"type": "source", "name": name, "kind": kind, "status": status, "detail": detail})
        if status != "checking":
            self.s.report.sources.append(SourceStatus(name=name, kind=kind, status=status, detail=detail))

    def add(self, *, type_: str, category: str, value: str, url: str, source_name: str, evidence: str,
            confidence: float, sensitivity: str, reasons: list[str], group: str | None, label: str | None = None,
            mismatches: list[str] | None = None, source_title: str = "") -> None:
        key = (type_, value.lower().strip(), url)
        if key in self._keys or len(self.findings) >= MAX_FINDINGS:
            return
        if type_ == "mention":                            # plain mentions are low value: don't let them crowd out
            if self._mentions >= MAX_MENTIONS:
                return
            self._mentions += 1
        self._keys.add(key)
        matches = value_matches_input(type_, value, self.f)
        if matches:   # your own phone/email on the page: strong, strongest when your name is there too
            named = bool(set(reasons) & {"full name", "other name", "name (split)"})
            confidence = max(confidence, 0.9 if named else 0.6)
            reasons = sorted(set(reasons) | {type_})
        finding = Finding(
            id=f"f{next(self._ids)}", category=category, type=type_,
            label=label or LABELS.get(type_, type_.title()),
            value_masked=redact(mask(type_, value)), source_url=url, source_name=source_name,
            source_title=redact(source_title)[:120], evidence=redact(evidence)[:300],
            confidence=round(confidence, 2), confidence_label=confidence_label(confidence), sensitivity=sensitivity,
            risk="green", matches_input=matches, match_reasons=reasons, mismatch_reasons=list(mismatches or []),
            removal=playbook_for(self.cfg, category=category, type_=type_, group=group, url=url),
        )
        rescore([finding])
        self.findings.append(finding)
        self.s.emit({"type": "finding", "finding": finding.model_dump()})

    # ── pipeline ────────────────────────────────────────────────────────────
    async def run(self) -> None:
        self.stage("plan", "Planning searches")
        b = self.cfg.budget
        queries = build_queries(self.f, self.level, b.get("max_queries", 24))
        self.s.emit({"type": "plan", "count": len(queries), "purposes": [q.purpose for q in queries]})

        probe_task = asyncio.create_task(self.run_probes())

        self.stage("search", f"Searching the web ({len(queries)} searches)")
        candidates = await self.run_searches(queries)

        await self.read_pages(candidates)

        if self.f.email or self.f.usernames:
            self.stage("probe", "Checking breaches and accounts")
        await probe_task

        self.stage("score", "Scoring your exposure")
        self.finish()

    async def run_searches(self, queries) -> list[Candidate]:
        sem = asyncio.Semaphore(self.cfg.search.get("concurrency", 5))
        loc, lang = self.f.country, self.cfg.search.get("language", "en")
        found: dict[str, Candidate] = {}

        async def one(q):
            async with sem:
                self.source(q.purpose, "search", "checking")
                try:
                    hits = await self.tf.search(q.text, location=loc, language=lang, include_domains=q.include_domains)
                except TinyFishError as exc:
                    self.partial = True
                    self.source(q.purpose, "search", "failed", exc.code or str(exc))
                    return
                kept = 0
                for h in hits:
                    c = self._candidate(h)
                    if not c:
                        continue
                    kept += 1
                    url = _normal_url(h.url)
                    prev = found.get(url)
                    if prev is None or c.confidence > prev.confidence:
                        c.purposes = (prev.purposes if prev else set())
                        found[url] = c
                    found[url].purposes.add(q.purpose)
                self.source(q.purpose, "search", "ok", f"{kept} relevant of {len(hits)} results")

        await asyncio.gather(*(one(q) for q in queries))
        priority = {"broker": 0, "documents": 1, "professional": 2, "social": 3, "code": 4}
        return sorted(found.values(), key=lambda c: (-c.confidence, priority.get(c.group or "", 5)))

    def _candidate(self, h: Hit) -> Candidate | None:
        domain = (urlparse(h.url).hostname or "").removeprefix("www.")
        if not domain or self.cfg.domain_in(domain, "ignore_domains"):
            return None
        m = page_match(f"{h.title}\n{h.snippet}", h.url, self.f)
        if not set(m.reasons) & IDENTIFYING:             # a city or employer alone isn't about *you*
            return None
        return Candidate(hit=h, domain=domain, group=self.cfg.group_for(domain), confidence=m.confidence,
                         reasons=m.reasons)

    async def read_pages(self, candidates: list[Candidate]) -> None:
        limit = self.cfg.budget.get("max_fetch_urls", 20)
        fetchable = [c for c in candidates if not self.cfg.domain_in(c.domain, "snippet_only_domains")]
        to_fetch, snippet_only = fetchable[:limit], [c for c in candidates if c not in fetchable[:limit]]
        if len(fetchable) > limit:
            self.partial = True
        self.stage("fetch", f"Reading the top {len(to_fetch)} of {len(candidates)} pages that mention you")

        for c in snippet_only:                     # login-walled or over budget: use what search showed
            self.from_text(c, f"{c.hit.title}\n{c.hit.snippet}", fetched=False)

        batches = [to_fetch[i:i + 10] for i in range(0, len(to_fetch), 10)]
        await asyncio.gather(*(self.fetch_batch(batch) for batch in batches))

    async def fetch_batch(self, batch: list[Candidate]) -> None:
        by_url = {c.hit.url: c for c in batch}
        for c in batch:
            self.source(_short(c), "fetch", "checking")
        try:
            results, errors = await self.tf.fetch(list(by_url))
        except TinyFishError as exc:
            self.partial = True
            for c in batch:
                self.source(_short(c), "fetch", "failed", exc.code or "fetch unavailable")
                self.from_text(c, f"{c.hit.title}\n{c.hit.snippet}", fetched=False)
            return

        done: set[str] = set()
        for r in results:
            c = by_url.get(r.get("url")) or by_url.get(r.get("final_url"))
            if not c:
                continue
            done.add(c.hit.url)
            text = r.get("text")
            text = text if isinstance(text, str) else str(text or "")
            self.source(_short(c), "fetch", "ok")
            self.from_text(c, f"{c.hit.title}\n{c.hit.snippet}\n{text[:60000]}", fetched=True, title=r.get("title") or c.hit.title)

        for e in errors:
            c = by_url.get(e.get("url"))
            if not c or c.hit.url in done:
                continue
            done.add(c.hit.url)
            code = e.get("error") or e.get("code") or "error"
            blocked = code in ("login_required", "bot_blocked")
            if blocked and c.group == "broker" and await self.try_agent(c):
                continue
            self.source(_short(c), "fetch", "blocked" if blocked else "failed", code)
            self.from_text(c, f"{c.hit.title}\n{c.hit.snippet}", fetched=False)

        for url, c in by_url.items():               # anything the API silently dropped
            if url not in done:
                self.from_text(c, f"{c.hit.title}\n{c.hit.snippet}", fetched=False)

    async def try_agent(self, c: Candidate) -> bool:
        """Paid fallback for people-finder pages that block plain fetching. Off unless agent_enabled."""
        b = self.cfg.budget
        if not b.get("agent_enabled") or self.agent_runs >= b.get("max_agent_runs", 1):
            return False
        self.agent_runs += 1
        self.source(_short(c), "agent", "checking")
        goal = (
            f'Read this page. If it shows a person named "{self.f.full_name}", extract only the details it '
            "publicly displays about them. Do not log in, sign up, pay, or submit any form. If a login, paywall "
            'or captcha appears, stop and return {"blocked": true}.'
        )
        schema = {"type": "object", "properties": {
            "blocked": {"type": "boolean"}, "name": {"type": "string"}, "phone": {"type": "string"},
            "email": {"type": "string"}, "address": {"type": "string"}, "city": {"type": "string"},
            "age": {"type": "string"}, "relatives": {"type": "array", "items": {"type": "string"}},
            "employer": {"type": "string"}}}
        try:
            run = await self.tf.agent(c.hit.url, goal, schema, b.get("agent_max_seconds", 60))
        except TinyFishError as exc:
            self.source(_short(c), "agent", "failed", exc.code or str(exc))
            return False
        self.cost += (run.get("num_of_steps") or 0) * b.get("agent_cost_per_step_usd", 0.016)
        result = run.get("result") or {}
        if run.get("status") != "COMPLETED" or not isinstance(result, dict) or result.get("blocked"):
            self.source(_short(c), "agent", "blocked", "page needs login or captcha")
            return False
        lines = [f"{self.f.full_name}"]
        for k in ("phone", "email", "address", "city", "age", "employer"):
            if result.get(k):
                lines.append(f"{'Location' if k == 'city' else k.title()}: {result[k]}")
        if result.get("relatives"):
            lines.append("Relatives: " + ", ".join(result["relatives"]))
        self.source(_short(c), "agent", "ok", f"{run.get('num_of_steps') or 0} steps")
        self.from_text(c, "\n".join(lines) + f"\n{c.hit.title}\n{c.hit.snippet}", fetched=True)
        return True

    def from_text(self, c: Candidate, text: str, *, fetched: bool, title: str = "") -> None:
        m = page_match(text, c.hit.url, self.f)       # text always includes the search title + snippet
        common = dict(url=c.hit.url, source_name=c.hit.site_name or c.domain, source_title=title or c.hit.title,
                      confidence=m.confidence, reasons=m.reasons, mismatches=m.mismatches, group=c.group)

        ptype, pcat, psens = PRESENCE.get(c.group or "", ("mention", "identity", "low"))
        if ptype == "profile" and not is_profile_url(c.hit.url):
            ptype, pcat, psens = "mention", pcat, "low"          # a post or thread that mentions you
        if c.hit.url.lower().split("?")[0].endswith(".pdf"):
            ptype, pcat, psens = "document", "identity", "medium"
        self.add(type_=ptype, category=pcat, value=c.hit.title[:90] or c.domain, evidence=c.hit.snippet,
                 sensitivity=psens, label=f"{LABELS[ptype]} on {common['source_name']}", **common)

        if m.confidence < MIN_PAGE_CONFIDENCE_FOR_DETAILS:
            return
        for dp in extract(text, self.f, title=title or c.hit.title):
            sensitivity = dp.sensitivity
            if dp.type == "location" and self.f.city.lower() in dp.value.lower():
                sensitivity = "low"                      # just the city you told us
            self.add(type_=dp.type, category=dp.category, value=dp.value, evidence=dp.evidence,
                     sensitivity=sensitivity, label=f"{LABELS.get(dp.type, dp.type.title())} on {common['source_name']}",
                     **common)

    async def run_probes(self) -> None:
        timeout = self.cfg.timeouts.get("probe", 8)
        jobs = []
        if self.f.email:
            jobs += [self.probe_breaches(timeout), self.probe_gravatar(timeout)]
        jobs += [self.probe_usernames(u, timeout) for u in self.f.usernames]
        await asyncio.gather(*jobs)

    async def probe_breaches(self, timeout: float) -> None:
        name = "Data breach databases"
        self.source(name, "breach", "checking")
        try:
            res = await probes.check_breaches(self.http, self.f.email, timeout)
        except (httpx.HTTPError, ValueError) as exc:
            self.partial = True
            self.source(name, "breach", "failed", type(exc).__name__)
            return
        self.source(name, "breach", "ok", f"{len(res.breaches)} breaches")
        if not res.breaches:
            return
        exposed = ", ".join(res.exposed_data[:8]) or "unknown fields"
        has_pw = any("password" in d.lower() for d in res.exposed_data)
        shown = ", ".join(res.breaches[:12]) + (" …" if len(res.breaches) > 12 else "")
        self.add(type_="breach", category="breach", value=f"{len(res.breaches)} breaches", url="https://xposedornot.com/",
                 source_name="XposedOrNot", evidence=f"Breaches: {shown}. Exposed data: {exposed}.",
                 confidence=0.95, sensitivity="high" if has_pw or len(res.breaches) >= 3 else "medium",
                 reasons=["email"], group=None,
                 label=f"Your email is in {len(res.breaches)} data breach{'es' if len(res.breaches) != 1 else ''}")

    async def probe_gravatar(self, timeout: float) -> None:
        self.source("Gravatar", "probe", "checking")
        try:
            hit = await probes.check_gravatar(self.http, self.f.email, timeout)
        except (httpx.HTTPError, ValueError) as exc:
            self.source("Gravatar", "probe", "failed", type(exc).__name__)
            return
        self.source("Gravatar", "probe", "ok", "profile found" if hit else "no profile")
        if hit:
            bits = [b for b in (hit.display_name, hit.location) if b]
            self.add(type_="profile", category="social", value=hit.profile_url, url=hit.profile_url,
                     source_name="Gravatar", evidence="Public profile linked to your email. " + " · ".join(bits),
                     confidence=0.9, sensitivity="medium", reasons=["email"], group="social",
                     label="Public Gravatar profile linked to your email")

    async def probe_usernames(self, username: str, timeout: float) -> None:
        platforms = self.cfg.sources.get("username_platforms", [])
        name = f"“{username}” on {len(platforms)} platforms"
        self.source(name, "probe", "checking")
        hits, failures = await probes.probe_usernames(self.http, username, platforms, timeout)
        detail = f"found on {len(hits)}" + (f", {len(failures)} unreachable" if failures else "")
        self.source(name, "probe", "ok", detail)
        for h in hits:
            m = page_match(f"{h.display_name or ''}\n{h.location or ''}", h.profile_url, self.f)
            conf = max(m.confidence, 0.4)            # an exact username match is decent evidence on its own
            ev = f"An account named “{username}” exists on {h.platform}."
            if h.display_name:
                ev += f" Display name: {h.display_name}."
            if h.location:
                ev += f" Location: {h.location}."
            self.add(type_="username", category=h.category, value=h.profile_url, url=h.profile_url,
                     source_name=h.platform, source_title=h.display_name or username, evidence=ev, confidence=conf,
                     sensitivity="medium" if len(m.reasons) > 1 else "low", reasons=m.reasons,
                     mismatches=m.mismatches, group=h.category, label=f"Account with your username on {h.platform}")

    def finish(self) -> None:
        r = self.s.report
        r.findings = sorted(self.findings, key=lambda x: ({"red": 0, "amber": 1, "green": 2}[x.risk], -x.confidence))
        r.score, r.score_label, r.counts = rescore(r.findings)
        r.summary = summarise(r.findings, r.score, r.score_label, r.counts)
        r.partial = self.partial
        r.cost_usd = round(self.cost, 3)
        r.status = "done"
        r.finished_at = datetime.now(timezone.utc).isoformat()


async def run_scan(session: Session, settings: Settings, tf: TinyFishClient, http: httpx.AsyncClient) -> None:
    scan = Scan(session, settings, tf, http)
    try:
        await scan.run()
        session.emit({"type": "done", "report": session.report.model_dump()})
    except asyncio.CancelledError:
        raise
    except CircuitOpen:
        scan.partial = True
        scan.finish()
        session.emit({"type": "done", "report": session.report.model_dump()})
    except Exception:
        log.exception("scan %s failed", session.id)
        session.report.status = "failed"
        session.emit({"type": "error", "message": "Something went wrong during the scan. Please try again."})


PROFILE_PATTERNS = [
    re.compile(p) for p in (
        r"linkedin\.com/in/[^/]+/?$", r"(?:x|twitter)\.com/[A-Za-z0-9_]+/?$", r"instagram\.com/[A-Za-z0-9_.]+/?$",
        r"facebook\.com/(?:profile\.php\?id=\d+|[A-Za-z0-9.]+/?$)", r"reddit\.com/(?:u|user)/[^/]+/?$",
        r"(?:github|gitlab)\.com/[A-Za-z0-9-]+/?$", r"youtube\.com/(?:@|c/|channel/|user/)[^/]+/?$",
        r"threads\.net/@[^/]+/?$", r"medium\.com/@[^/]+/?$", r"tiktok\.com/@[^/]+/?$", r"pinterest\.[a-z.]+/[^/]+/?$",
        r"(?:crunchbase\.com/person|wellfound\.com/u|naukri\.com/[^/]*profile)",
    )
]


def is_profile_url(url: str) -> bool:
    u = url.split("#")[0].lower()
    return any(p.search(u) for p in PROFILE_PATTERNS)


def _short(c: Candidate) -> str:
    """Readable, unique-ish label for a fetched page in the live feed."""
    path = urlparse(c.hit.url).path.strip("/")
    return f"{c.domain}/{path[:28]}{'…' if len(path) > 28 else ''}" if path else c.domain


def _normal_url(url: str) -> str:
    p = urlparse(url)
    return f"{(p.hostname or '').removeprefix('www.')}{p.path.rstrip('/')}".lower()
