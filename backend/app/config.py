"""Settings: config.yaml + config/*.yaml for behaviour, environment variables for secrets."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE lines; real env vars win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text()) or {} if path.exists() else {}


@dataclass(frozen=True)
class Settings:
    tinyfish_api_key: str
    session_ttl_minutes: int
    scans_per_hour_per_ip: int
    search: dict[str, Any]
    budget: dict[str, Any]
    timeouts: dict[str, float]
    circuit_breaker: dict[str, int]
    sources: dict[str, Any]
    playbooks: dict[str, Any]
    user_agent: str = "FingerprintBot/0.1 (+self-privacy scan; contact via repo)"
    domain_group_index: dict[str, str] = field(default_factory=dict)

    def group_for(self, domain: str) -> str | None:
        """Return the domain group ('social', 'broker', ...) for a host, matching parent domains."""
        parts = domain.lower().split(".")
        for i in range(len(parts) - 1):
            group = self.domain_group_index.get(".".join(parts[i:]))
            if group:
                return group
        return None

    def domain_in(self, domain: str, key: str) -> bool:
        domain = domain.lower()
        return any(domain == d or domain.endswith("." + d) for d in self.sources.get(key, []))


@lru_cache
def get_settings() -> Settings:
    _load_dotenv(ROOT / ".env")
    cfg = _yaml(ROOT / "config.yaml")
    sources = _yaml(ROOT / "config" / "sources.yaml")
    playbooks = _yaml(ROOT / "config" / "playbooks.yaml")

    def env_int(name: str, default: int) -> int:
        return int(os.environ.get(name.upper(), default))

    budget = dict(cfg.get("budget", {}))
    if "AGENT_ENABLED" in os.environ:
        budget["agent_enabled"] = os.environ["AGENT_ENABLED"].lower() in ("1", "true", "yes")

    index: dict[str, str] = {}
    for group, domains in (sources.get("domain_groups") or {}).items():
        for d in domains:
            index.setdefault(d.lower(), group)

    return Settings(
        tinyfish_api_key=os.environ.get("TINYFISH_API_KEY", ""),
        session_ttl_minutes=env_int("session_ttl_minutes", cfg.get("session_ttl_minutes", 30)),
        scans_per_hour_per_ip=env_int("scans_per_hour_per_ip", cfg.get("scans_per_hour_per_ip", 10)),
        search=cfg.get("search", {}),
        budget=budget,
        timeouts=cfg.get("timeouts_seconds", {}),
        circuit_breaker=cfg.get("circuit_breaker", {}),
        sources=sources,
        playbooks=playbooks,
        domain_group_index=index,
    )
