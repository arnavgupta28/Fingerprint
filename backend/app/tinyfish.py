"""Thin async client for TinyFish Search / Fetch / Agent with retries and a circuit breaker.

Docs: https://docs.tinyfish.ai/for-coding-agents
- Search  GET  https://api.search.tinyfish.ai        free within daily allowance
- Fetch   POST https://api.fetch.tinyfish.ai         free within daily allowance, max 10 URLs per call
- Agent   POST https://agent.tinyfish.ai/v1/automation/run   wallet, $0.016 per step
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger("fingerprint.tinyfish")

SEARCH_URL = "https://api.search.tinyfish.ai"
FETCH_URL = "https://api.fetch.tinyfish.ai"
AGENT_URL = "https://agent.tinyfish.ai/v1/automation/run"


class TinyFishError(Exception):
    def __init__(self, message: str, status: int | None = None, code: str | None = None):
        super().__init__(message)
        self.status = status
        self.code = code


class CircuitOpen(TinyFishError):
    pass


class CircuitBreaker:
    def __init__(self, failures_to_open: int = 3, open_seconds: int = 300):
        self.threshold = failures_to_open
        self.open_seconds = open_seconds
        self.failures = 0
        self.opened_at: float | None = None

    @property
    def is_open(self) -> bool:
        if self.opened_at is None:
            return False
        if time.monotonic() - self.opened_at > self.open_seconds:
            self.opened_at, self.failures = None, 0   # half-open: let the next call try
            return False
        return True

    def success(self) -> None:
        self.failures, self.opened_at = 0, None

    def failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = time.monotonic()


@dataclass
class Hit:
    url: str
    title: str
    snippet: str
    site_name: str
    position: int


class TinyFishClient:
    RETRY_STATUSES = {429, 500, 502, 503, 504}

    def __init__(self, api_key: str, timeouts: dict[str, float], breaker_cfg: dict[str, int], user_agent: str):
        if not api_key:
            raise RuntimeError("TINYFISH_API_KEY is not set")
        self._headers = {"X-API-Key": api_key, "User-Agent": user_agent}
        self._timeouts = timeouts
        self._http = httpx.AsyncClient(headers=self._headers)
        self.breakers = {name: CircuitBreaker(**breaker_cfg) for name in ("search", "fetch", "agent")}

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _request(self, product: str, method: str, url: str, retries: int = 2, **kwargs) -> dict[str, Any]:
        breaker = self.breakers[product]
        if breaker.is_open:
            raise CircuitOpen(f"{product} temporarily disabled after repeated failures", code="CIRCUIT_OPEN")
        timeout = self._timeouts.get(product, 30)
        for attempt in range(retries + 1):
            try:
                resp = await self._http.request(method, url, timeout=timeout, **kwargs)
            except httpx.TransportError as exc:
                if attempt < retries:
                    await asyncio.sleep(0.5 * 2**attempt)
                    continue
                breaker.failure()
                raise TinyFishError(f"{product} unreachable: {type(exc).__name__}") from exc
            if resp.status_code in self.RETRY_STATUSES and attempt < retries:
                retry_after = float(resp.headers.get("Retry-After", 0.5 * 2**attempt))
                await asyncio.sleep(min(retry_after, 5))
                continue
            if resp.status_code >= 400:
                body = _safe_json(resp)
                err = body.get("error") if isinstance(body.get("error"), dict) else {}
                code = err.get("code") or body.get("code")
                if resp.status_code >= 500 or resp.status_code == 429:
                    breaker.failure()
                raise TinyFishError(f"{product} HTTP {resp.status_code} {code or ''}".strip(), resp.status_code, code)
            breaker.success()
            return _safe_json(resp)
        raise TinyFishError(f"{product} failed after retries")

    async def search(self, query: str, *, location: str, language: str,
                     include_domains: str | None = None, page: int = 0) -> list[Hit]:
        params = {"query": query, "location": location, "language": language, "page": page}
        if include_domains:
            params["include_domains"] = include_domains
        data = await self._request("search", "GET", SEARCH_URL, params=params)
        return [
            Hit(url=r.get("url", ""), title=r.get("title") or "", snippet=r.get("snippet") or "",
                site_name=r.get("site_name") or "", position=r.get("position") or 0)
            for r in data.get("results", []) if r.get("url")
        ]

    async def fetch(self, urls: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Return (results, errors). Each error has url + code (login_required, bot_blocked, ...)."""
        data = await self._request("fetch", "POST", FETCH_URL, retries=1,
                                   json={"urls": urls[:10], "format": "markdown"})
        return data.get("results", []), data.get("errors", [])

    async def agent(self, url: str, goal: str, output_schema: dict | None, max_seconds: int) -> dict[str, Any]:
        body: dict[str, Any] = {"url": url, "goal": goal, "agent_config": {"max_duration_seconds": max_seconds}}
        if output_schema:
            body["output_schema"] = output_schema
        return await self._request("agent", "POST", AGENT_URL, retries=0, json=body)


def _safe_json(resp: httpx.Response) -> dict[str, Any]:
    try:
        data = resp.json()
        return data if isinstance(data, dict) else {"result": data}
    except ValueError:
        return {}
