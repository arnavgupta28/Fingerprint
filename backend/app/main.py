"""Fingerprint API: start a scan, stream progress, read the report, give verdicts, delete."""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .config import ROOT, get_settings
from .guardrails import PIIRedactingFilter, RateLimiter
from .models import Report, ScanRequest, VerdictRequest
from .pipeline.runner import run_scan
from .pipeline.score import rescore, summarise
from .session import SessionStore
from .tinyfish import TinyFishClient

handler = logging.StreamHandler()
handler.addFilter(PIIRedactingFilter())
handler.setFormatter(logging.Formatter('{"t":"%(asctime)s","lvl":"%(levelname)s","log":"%(name)s","msg":"%(message)s"}'))
logging.basicConfig(level=logging.INFO, handlers=[handler])
log = logging.getLogger("fingerprint")

settings = get_settings()
store = SessionStore(settings.session_ttl_minutes)
limiter = RateLimiter(settings.scans_per_hour_per_ip)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.tf = TinyFishClient(settings.tinyfish_api_key, settings.timeouts, settings.circuit_breaker,
                                  settings.user_agent)
    app.state.http = httpx.AsyncClient(headers={"User-Agent": settings.user_agent})
    yield
    await app.state.tf.aclose()
    await app.state.http.aclose()


app = FastAPI(title="Fingerprint", version="0.1.0", lifespan=lifespan)


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")


@app.post("/api/scan", status_code=202)
async def start_scan(body: ScanRequest, request: Request):
    if not limiter.allow(client_ip(request)):
        raise HTTPException(429, "Too many scans from your network. Please try again in an hour.")
    session = store.create(body, lambda sid: Report(
        scan_id=sid, level=body.level, status="running", started_at=datetime.now(timezone.utc).isoformat()))
    session.task = asyncio.create_task(run_scan(session, settings, request.app.state.tf, request.app.state.http))
    log.info("scan started level=%s", body.level)
    return {"scan_id": session.id}


@app.get("/api/scan/{sid}/stream")
async def stream(sid: str, request: Request):
    session = store.get(sid)
    if not session:
        raise HTTPException(404, "Scan not found or expired")
    queue: asyncio.Queue = asyncio.Queue()
    backlog = list(session.events)
    session.listeners.add(queue)

    async def gen():
        try:
            for event in backlog:
                yield _sse(event)
            if any(e["type"] in ("done", "error") for e in backlog):
                return
            while not await request.is_disconnected():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield _sse(event)
                if event["type"] in ("done", "error"):
                    return
        finally:
            session.listeners.discard(queue)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.get("/api/scan/{sid}/report", response_model=Report)
async def report(sid: str):
    session = store.get(sid)
    if not session:
        raise HTTPException(404, "Scan not found or expired")
    return session.report


@app.post("/api/scan/{sid}/verdict", response_model=Report)
async def verdict(sid: str, body: VerdictRequest):
    session = store.get(sid)
    if not session:
        raise HTTPException(404, "Scan not found or expired")
    r = session.report
    target = next((f for f in r.findings if f.id == body.finding_id), None)
    if not target:
        raise HTTPException(404, "Finding not found")
    target.user_verdict = body.verdict
    for f in r.findings:                               # a verdict is about the whole page / source
        if f.source_url == target.source_url and f.category != "breach":
            f.user_verdict = body.verdict
    r.score, r.score_label, r.counts = rescore(r.findings)
    r.summary = summarise(r.findings, r.score, r.score_label, r.counts)
    return r


@app.delete("/api/scan/{sid}", status_code=204)
async def delete(sid: str):
    store.delete(sid)


@app.get("/health")
async def health():
    tf = app.state.tf
    return {
        "status": "ok",
        "tinyfish_key": bool(settings.tinyfish_api_key),
        "breakers": {name: ("open" if b.is_open else "closed") for name, b in tf.breakers.items()},
        "active_scans": len(store),
        "agent_enabled": bool(settings.budget.get("agent_enabled")),
    }


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


# ── frontend ─────────────────────────────────────────────────────────────────
app.mount("/assets", StaticFiles(directory=ROOT / "assets"), name="assets")
app.mount("/static", StaticFiles(directory=ROOT / "frontend"), name="static")


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(ROOT / "frontend" / "index.html")
