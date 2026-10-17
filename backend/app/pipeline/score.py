"""⑥ Score: risk per finding, overall exposure score, removal playbooks and a plain-English summary."""
from __future__ import annotations

import math

from ..config import Settings
from ..models import Finding, Removal

SENSITIVITY_WEIGHT = {"high": 10, "medium": 5, "low": 2}

LABELS = {
    "phone": "Phone number", "email": "Email address", "address": "Home address", "dob": "Date of birth",
    "age": "Age", "location": "Location", "employer": "Workplace", "education": "School / college",
    "family": "Family member", "profile": "Public profile", "listing": "People-finder listing",
    "document": "Document mentioning you", "mention": "Mention of your name", "breach": "Data breach",
    "username": "Account with your username",
}


def risk_for(sensitivity: str, confidence: float) -> str:
    if sensitivity == "high":                 # name + city is enough to flag a phone/address/listing
        return "red" if confidence >= 0.4 else "amber"
    if sensitivity == "medium":
        return "amber" if confidence >= 0.5 else "green"
    return "green"


def playbook_for(settings: Settings, *, category: str, type_: str, group: str | None, url: str) -> Removal:
    if category == "breach":
        key = "breach_response"
    elif "gravatar.com" in url:
        key = "gravatar_privacy"
    elif group == "broker":
        key = "peoplefinder_optout"
    elif group == "social":
        key = "social_lockdown"
    elif group == "professional":
        key = "professional_visibility"
    elif group == "code":
        key = "code_privacy"
    elif group == "documents" or url.lower().split("?")[0].endswith((".pdf", ".doc", ".docx")):
        key = "old_document"
    elif group == "news":
        key = "news_mention"
    elif type_ in ("phone", "email", "address"):
        key = "google_results_removal"
    else:
        key = "generic"
    pb = settings.playbooks.get(key) or settings.playbooks["generic"]
    return Removal(playbook=key, title=pb["title"], steps=pb["steps"])


def effective_confidence(f: Finding) -> float:
    if f.user_verdict == "me":
        return 1.0
    if f.user_verdict == "not_me":
        return 0.0
    return f.confidence


def rescore(findings: list[Finding]) -> tuple[int, str, dict[str, int]]:
    counts = {"red": 0, "amber": 0, "green": 0}
    total = 0.0
    for f in findings:
        conf = effective_confidence(f)
        f.risk = risk_for(f.sensitivity, conf)  # type: ignore[assignment]
        if f.user_verdict == "not_me":
            continue
        counts[f.risk] += 1
        total += SENSITIVITY_WEIGHT[f.sensitivity] * conf
    score = round(100 * (1 - math.exp(-total / 40)))
    label = "Low" if score < 25 else "Moderate" if score < 50 else "High" if score < 75 else "Very high"
    return score, label, counts


def summarise(findings: list[Finding], score: int, label: str, counts: dict[str, int]) -> str:
    live = [f for f in findings if f.user_verdict != "not_me"]
    if not live:
        return "Good news: we didn't find anything public that's clearly about you. Smudge is impressed!"
    reds = [f for f in live if f.risk == "red"]
    parts = [f"We found {len(live)} public item{'s' if len(live) != 1 else ''} that may be about you."]
    if reds:
        kinds = sorted({LABELS.get(f.type, f.type).lower() for f in reds})
        parts.append(f"{len(reds)} {'is' if len(reds) == 1 else 'are'} high-risk ({', '.join(kinds[:4])}).")
    unsure = sum(1 for f in live if f.user_verdict is None and f.confidence < 0.5)
    if unsure:
        parts.append(f"Tap “Is this you?” on {unsure} uncertain item{'s' if unsure != 1 else ''} to sharpen your score.")
    parts.append(f"Exposure: {label.lower()} ({score}/100).")
    return " ".join(parts)
