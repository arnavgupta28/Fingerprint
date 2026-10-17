"""Free public checks that don't need TinyFish: data breaches, Gravatar, username reuse."""
from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from typing import Any

import httpx

XON_CHECK = "https://api.xposedornot.com/v1/check-email/{email}"
XON_ANALYTICS = "https://api.xposedornot.com/v1/breach-analytics"
GRAVATAR = "https://gravatar.com/{hash}.json"


@dataclass
class BreachResult:
    breaches: list[str] = field(default_factory=list)
    exposed_data: list[str] = field(default_factory=list)   # e.g. ["Passwords", "Phone numbers"]
    risk_label: str | None = None


@dataclass
class ProfileHit:
    platform: str
    platform_id: str
    profile_url: str
    category: str
    display_name: str | None = None
    location: str | None = None


async def check_breaches(http: httpx.AsyncClient, email: str, timeout: float) -> BreachResult:
    """XposedOrNot: free, no key. Only the email is sent; nothing else."""
    resp = await http.get(XON_CHECK.format(email=email), timeout=timeout)
    if resp.status_code == 404:
        return BreachResult()
    resp.raise_for_status()
    data = resp.json()
    names: list[str] = []
    for group in data.get("breaches") or []:
        names.extend(group if isinstance(group, list) else [group])
    if not names:
        return BreachResult()

    result = BreachResult(breaches=names)
    try:
        a = await http.get(XON_ANALYTICS, params={"email": email}, timeout=timeout)
        metrics = a.json().get("BreachMetrics", {}) if a.status_code == 200 else {}
        risk = (metrics.get("risk") or [{}])[0]
        result.risk_label = risk.get("risk_label")
        result.exposed_data = sorted(_leaf_names(metrics.get("xposed_data") or []))
    except (httpx.HTTPError, ValueError, AttributeError, IndexError):
        pass
    return result


def _leaf_names(nodes: list[Any]) -> set[str]:
    out: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict):
            continue
        name = node.get("name", "")
        if name.startswith("data_"):
            out.add(name[5:])
        out |= _leaf_names(node.get("children") or [])
    return out


async def check_gravatar(http: httpx.AsyncClient, email: str, timeout: float) -> ProfileHit | None:
    digest = hashlib.sha256(email.strip().lower().encode()).hexdigest()   # only a hash is sent
    resp = await http.get(GRAVATAR.format(hash=digest), timeout=timeout, follow_redirects=True)
    if resp.status_code != 200:
        return None
    try:
        entry = (resp.json().get("entry") or [{}])[0]
    except (ValueError, IndexError):
        return None
    return ProfileHit(
        platform="Gravatar", platform_id="gravatar",
        profile_url=entry.get("profileUrl") or f"https://gravatar.com/{digest}",
        category="social", display_name=entry.get("displayName"),
        location=entry.get("currentLocation"),
    )


async def probe_usernames(http: httpx.AsyncClient, username: str, platforms: list[dict[str, Any]],
                          timeout: float) -> tuple[list[ProfileHit], list[tuple[str, str]]]:
    """Check which platforms have an account with this exact username. Returns (hits, failures)."""

    async def one(p: dict[str, Any]):
        resp = await http.get(p["url"].format(username=username), timeout=timeout, follow_redirects=True)
        rule = p.get("exists_when", "status_200")
        exists = False
        display = location = None
        if resp.status_code == 200:
            data: Any = None
            try:
                data = resp.json()
            except ValueError:
                pass
            if rule == "status_200":
                exists = True
            elif rule == "json_nonempty":
                exists = bool(data)
            elif rule == "json_not_null":
                exists = data is not None
            elif rule == "keybase":
                exists = bool(data and any(data.get("them") or []))
            if exists and isinstance(data, dict):
                inner = data["data"] if isinstance(data.get("data"), dict) else data
                display, location = inner.get("name"), inner.get("location")
            elif exists and isinstance(data, list) and data and isinstance(data[0], dict):
                display = data[0].get("name")
        elif resp.status_code not in (404, 410):
            raise httpx.HTTPStatusError(f"HTTP {resp.status_code}", request=resp.request, response=resp)
        if not exists:
            return None
        return ProfileHit(platform=p["name"], platform_id=p["id"],
                          profile_url=p["profile"].format(username=username),
                          category=p.get("category", "social"), display_name=display, location=location)

    results = await asyncio.gather(*(one(p) for p in platforms), return_exceptions=True)
    hits, failures = [], []
    for p, r in zip(platforms, results):
        if isinstance(r, BaseException):
            failures.append((p["name"], type(r).__name__))
        elif r is not None:
            hits.append(r)
    return hits, failures
