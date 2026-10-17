"""⑤ Match: how sure are we that a page is about *you* and not a namesake?

Weighted evidence, the way entity-resolution and people-search tools do it (see docs/INPUT-FIELDS.md):
unique identifiers (phone, email, username) count most, the name is necessary but weak, location / age / work /
school corroborate, and contradictions (an age that doesn't fit your birth year) count against.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from ..models import ScanFields
from .extract import PHONE, name_anchors

WEIGHTS = {
    # unique identifiers
    "phone": 0.55,
    "email": 0.50,
    "username": 0.30,
    # name
    "full name": 0.25,
    "other name": 0.25,
    "name (split)": 0.12,
    "middle name": 0.05,
    # corroborating
    "age": 0.20,
    "city": 0.15,
    "employer": 0.15,
    "school": 0.10,
    "past city": 0.08,
    "state": 0.05,
}
PENALTIES = {
    "age doesn't match": 0.35,
    "different middle initial": 0.10,
    "page lists many people's numbers": 0.15,
}
DIRECTORY_PHONES = 8   # more distinct numbers than this → a phone directory, not a page about one person
STRONG = {"phone", "email", "username"}
NAME = {"full name", "other name", "name (split)"}

AGE_NEAR = re.compile(r"\b(?:age[d:]?\s*(\d{2})|(\d{2})\s*(?:years old|yrs old|y/o|yo\b)|born(?: in)?\s+(?:[A-Za-z]+\s+)?(?:\d{1,2},?\s+)?((?:19|20)\d\d))", re.I)
MIDDLE_INITIAL = r"\b{first}\s+([A-Z])\.?\s+{last}\b"


@dataclass
class Match:
    confidence: float
    reasons: list[str]
    mismatches: list[str]


def confidence_label(conf: float) -> str:
    if conf >= 0.75:
        return "Very likely you"
    if conf >= 0.5:
        return "Likely you"
    if conf >= 0.3:
        return "Maybe you"
    return "Probably not you"


def page_match(text: str, url: str, f: ScanFields) -> Match:
    """Score how likely a page (or snippet) is about this user. Reasons are shown on each source card."""
    low = f"{text}\n{url}".lower()
    reasons: list[str] = []
    mismatches: list[str] = []

    # name: exact full name, an alias / name with middle, or first + last close together
    if _word_in(f.full_name, low):
        reasons.append("full name")
    elif any(_word_in(n, low) for n in f.names[1:]):
        reasons.append("other name")
    elif any(name_anchors(text, n) for n in f.names):
        reasons.append("name (split)")

    if f.middle_name:
        first, last = f.full_name.split()[0], f.full_name.split()[-1]
        if _word_in(f"{first} {f.middle_name} {last}", low):
            reasons.append("middle name")
        else:
            m = re.search(MIDDLE_INITIAL.format(first=re.escape(first), last=re.escape(last)), text, re.I)
            if m:
                if m.group(1).upper() == f.middle_name[0].upper():
                    reasons.append("middle name")
                else:
                    mismatches.append("different middle initial")

    # unique identifiers
    if any(re.sub(r"\D", "", m.group(0)).endswith(f.phone_local[-9:]) for m in PHONE.finditer(text)):
        reasons.append("phone")
    if f.email and f.email in low:
        reasons.append("email")
    if any(_username_in(u, f, text, url) for u in f.usernames):
        reasons.append("username")

    # corroborating
    if f.city and _word_in(f.city, low):
        reasons.append("city")
    if f.state and _word_in(f.state, low):
        reasons.append("state")
    if any(_word_in(c, low) for c in f.past_cities):
        reasons.append("past city")
    if f.employer and _word_in(f.employer, low):
        reasons.append("employer")
    if f.school and _word_in(f.school, low):
        reasons.append("school")

    age_signal = _age_signal(text, f)
    if age_signal is True:
        reasons.append("age")
    elif age_signal is False:
        mismatches.append("age doesn't match")

    phones = {re.sub(r"\D", "", m.group(0))[-10:] for m in PHONE.finditer(text) if len(re.sub(r"\D", "", m.group(0))) >= 10}
    if len(phones) > DIRECTORY_PHONES:
        mismatches.append("page lists many people's numbers")

    score = sum(WEIGHTS[r] for r in reasons) - sum(PENALTIES[m] for m in mismatches)
    rs = set(reasons)
    if not rs & NAME:
        score = min(score, 0.7)               # without your name on the page we can't be "very" sure
    if not rs & STRONG:
        if rs <= NAME | {"middle name"}:
            score = min(score, 0.35)          # a name alone: many people share it
        elif len(rs - NAME - {"middle name"}) == 1:
            score = min(score, 0.6)           # name + one corroborating detail
    return Match(round(max(0.03, min(0.98, score)), 2), reasons, mismatches)


def page_confidence(text: str, url: str, f: ScanFields) -> tuple[float, list[str]]:
    m = page_match(text, url, f)
    return m.confidence, m.reasons


def value_matches_input(type_: str, value: str, f: ScanFields) -> bool:
    if type_ == "phone":
        return value.endswith(f.phone_local[-9:])
    if type_ == "email" and f.email:
        return value.lower() == f.email.lower()
    return False


def _age_signal(text: str, f: ScanFields) -> bool | None:
    """True if an age / birth year near your name fits, False if it contradicts, None if there's nothing to compare."""
    if not f.birth_year:
        return None
    anchors = [a for n in f.names for a in name_anchors(text, n)]
    if not anchors:
        return None
    this_year = date.today().year
    verdict = None
    for a in anchors[:20]:
        window = text[max(0, a - 250): a + 250]
        for m in AGE_NEAR.finditer(window):
            if m.group(3):
                ok = abs(int(m.group(3)) - f.birth_year) <= 1
            else:
                age = int(m.group(1) or m.group(2))
                ok = abs((this_year - age) - f.birth_year) <= 2
            if ok:
                return True
            verdict = False
    return verdict


def _username_in(username: str, f: ScanFields, text: str, url: str) -> bool:
    """A username that is just part of your name ("torvalds") only counts as a handle: in the URL or as @handle."""
    u = username.lower()
    name_parts = [p.lower() for p in f.full_name.split()]
    from_name = u in name_parts or re.sub(r"[._-]", "", u) in ("".join(name_parts), "".join(reversed(name_parts)))
    if re.search(rf"(?<![\w.-]){re.escape(u)}(?![\w-])", url.lower()) or f"@{u}" in text.lower():
        return True
    return not from_name and _word_in(u, text.lower())


def _word_in(needle: str, haystack: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(needle.lower())}(?!\w)", haystack) is not None
