"""④ Extract: find personal data points on a page, near a mention of the user. Rule-based (free, and no
personal data is sent to an LLM). Every data point keeps the quote it came from as evidence."""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..models import ScanFields

WINDOW = 350          # characters around a name mention that we treat as "about this person"
EVIDENCE = 90         # characters either side of a match kept as the evidence quote

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<![\d/])(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,5}\)?[\s.-]?)?\d{3,5}[\s.-]?\d{4,5}(?![\d/])")
DOB = re.compile(r"(?:born(?: on)?|date of birth|d\.?o\.?b\.?)[:\s]+([0-3]?\d[\s/.-][A-Za-z0-9]{1,9}[\s/.-](?:19|20)\d\d|[A-Z][a-z]+ [0-3]?\d,? (?:19|20)\d\d)", re.I)
AGE = re.compile(r"\b(?:age[d:]?\s*(\d{2})|(\d{2})\s*(?:years old|yrs old|y/o))\b", re.I)
PIN = re.compile(r"\b(\d{6}|\d{5}(?:-\d{4})?)\b")
STREET = re.compile(r"\b(?:flat|apt|apartment|house|h\.?no|plot|street|st\.|road|rd\.|lane|nagar|colony|sector|block|avenue|ave|marg|society|layout|cross|main)\b", re.I)
# A run of Capitalised Words (connectors allowed inside, never at the end; no sentence punctuation).
CAP = r"([A-Z][\w&'-]+(?:\s+(?:(?:of|and|&|for|the)\s+)?[A-Z][\w&'-]+){0,5})"
LOCATION = re.compile(r"\b(?i:lives in|living in|resides in|based in|located in|location[:\s]|hometown[:\s]|from)\s+" + CAP)
EMPLOYER = re.compile(r"\b(?i:works at|working at|employed at|employee at|engineer at|designer at|manager at|developer at|analyst at|consultant at|intern at|employer[:\s]|currently at)\s*" + CAP)
EDUCATION = re.compile(r"\b(?i:studied at|studies at|studying at|graduated from|alumn(?:us|a|i) of)\s*" + CAP
                       + r"|" + r"\b([A-Z][\w'-]*(?:\s+[A-Z][\w'-]*){0,5}\s+(?:University|College|Institute(?: of [A-Z][\w]*(?: [A-Z][\w]*)?)?|School|Academy))\b")
FAMILY = re.compile(r"\b(?i:son of|daughter of|wife of|husband of|father of|mother of|brother of|sister of|married to|spouse[:\s]|relatives?[:\s]|related to)\s*" + CAP)
LINKEDIN_TITLE = re.compile(r"^(?P<name>[^-|–]+)\s[-–]\s(?P<role>[^-|–]+?)(?:\s[-–]\s(?P<company>[^|]+?))?\s*\|\s*LinkedIn", re.I)


@dataclass
class DataPoint:
    type: str
    category: str
    value: str
    evidence: str
    sensitivity: str


def name_anchors(text: str, full_name: str) -> list[int]:
    """Positions where the user's name appears: exact, 'Last, First', or first+last close together."""
    low = text.lower()
    parts = full_name.lower().split()
    first, last = parts[0], parts[-1]
    anchors = [m.start() for m in re.finditer(re.escape(full_name.lower()), low)]
    anchors += [m.start() for m in re.finditer(re.escape(f"{last}, {first}"), low)]
    if not anchors:
        for m in re.finditer(rf"\b{re.escape(first)}\b", low):
            if re.search(rf"\b{re.escape(last)}\b", low[max(0, m.start() - 40): m.end() + 40]):
                anchors.append(m.start())
    return sorted(set(anchors))


def identifier_anchors(text: str, f: ScanFields) -> list[int]:
    low = text.lower()
    anchors: list[int] = []
    for ident in filter(None, [f.email, *[u.lower() for u in f.usernames]]):
        anchors += [m.start() for m in re.finditer(re.escape(ident.lower()), low)]
    anchors += [m.start() for m in PHONE.finditer(text) if _digits(m.group(0)).endswith(f.phone_local[-9:])]
    return anchors


def regions(text: str, anchors: list[int]) -> list[tuple[int, int]]:
    spans = sorted((max(0, a - WINDOW), min(len(text), a + WINDOW)) for a in anchors)
    merged: list[list[int]] = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged]


def extract(text: str, f: ScanFields, *, title: str = "") -> list[DataPoint]:
    """Extract data points that sit near a mention of the user (by name or by their identifiers)."""
    text = _clean(text)
    named = [a for n in f.names for a in name_anchors(text, n)]
    anchors = named + identifier_anchors(text, f)
    if not anchors:
        return []
    # Found only via your phone/email (no name on the page): nearby details may belong to anyone,
    # e.g. a phone directory. Keep just your own values.
    own_only = not named
    points: dict[tuple[str, str], DataPoint] = {}

    def add(type_, category, value, start, end, sensitivity, region_text):
        value = " ".join(value.split()).strip(" ,.;:-|")
        if len(value) < 2 or (type_ in WORDY and not _meaningful(value, f.names)):
            return
        key = (type_, _norm(type_, value))
        if own_only and not _is_own(type_, value, f):
            return
        if key not in points:
            ev = region_text[max(0, start - EVIDENCE): end + EVIDENCE].replace("\n", " ")
            points[key] = DataPoint(type_, category, value, "…" + " ".join(ev.split()) + "…", sensitivity)

    for s, e in regions(text, anchors):
        region = text[s:e]
        for m in EMAIL.finditer(region):
            if not _junk_email(m.group(0)):
                add("email", "contact", m.group(0).lower(), m.start(), m.end(), "medium", region)
        for m in PHONE.finditer(region):
            d = _digits(m.group(0))
            if 10 <= len(d) <= 13 and not _looks_like_date_or_id(m.group(0)) and not _toll_free(d):
                add("phone", "contact", d, m.start(), m.end(), "high", region)
        for m in DOB.finditer(region):
            add("dob", "identity", m.group(1), m.start(), m.end(), "high", region)
        for m in AGE.finditer(region):
            add("age", "identity", m.group(1) or m.group(2), m.start(), m.end(), "medium", region)
        for m in PIN.finditer(region):
            line_start = region.rfind("\n", 0, m.start()) + 1
            chunk = region[max(line_start, m.start() - 120): m.end()]
            if STREET.search(chunk):
                add("address", "location", chunk, m.start(), m.end(), "high", region)
        for m in LOCATION.finditer(region):
            add("location", "location", m.group(1), m.start(), m.end(), "medium", region)
        for m in EMPLOYER.finditer(region):
            add("employer", "work", m.group(1), m.start(), m.end(), "medium", region)
        for m in EDUCATION.finditer(region):
            add("education", "education", m.group(1) or m.group(2), m.start(), m.end(), "medium", region)
        for m in FAMILY.finditer(region):
            add("family", "family", m.group(1), m.start(), m.end(), "medium", region)

    lt = LINKEDIN_TITLE.search(title or "")
    if lt and any(name_anchors(lt.group("name"), n) for n in f.names):
        role = lt.group("role").strip()
        company = (lt.group("company") or "").strip()
        add("employer", "work", f"{role} at {company}" if company else role, 0, 0, "medium", title)

    return list(points.values())


WORDY = {"location", "employer", "education", "family"}
NOISE_WORDS = {
    "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec", "january",
    "february", "march", "april", "june", "july", "august", "september", "october", "november", "december",
    "follow", "share", "home", "about", "contact", "view", "more", "see", "the", "and", "msc", "bsc", "phd",
    "ba", "ma", "mba", "btech", "mtech", "present", "today", "here", "there", "linkedin", "facebook",
}


def _meaningful(value: str, names: list[str]) -> bool:
    """Drop junk captures like 'Jul', 'MSc', 'Follow' and the user's own name."""
    words = [w.lower().strip("'") for w in value.split()]
    if len(value) < 3 or all(w in NOISE_WORDS for w in words):
        return False
    return not any(value.lower() in n.lower() for n in names)


def _toll_free(digits: str) -> bool:
    """Business hotlines (1-800, 1800-…, 888, …) aren't personal numbers."""
    d = digits[1:] if digits.startswith("1") and len(digits) == 11 else digits
    return digits.startswith(("1800", "1860")) or d.startswith(("800", "888", "877", "866", "855", "844", "833"))


def _clean(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)            # markdown images
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)           # markdown links → text
    text = re.sub(r"[*_`#>]+", " ", text)
    return re.sub(r"[ \t]+", " ", text)


def _is_own(type_: str, value: str, f: ScanFields) -> bool:
    if type_ == "phone":
        return value.endswith(f.phone_local[-9:])
    return type_ == "email" and bool(f.email) and value.lower() == f.email


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def _norm(type_: str, value: str) -> str:
    if type_ == "phone":
        return value[-10:]
    return re.sub(r"\W+", "", value.lower())


def _junk_email(e: str) -> bool:
    e = e.lower()
    return any(x in e for x in ("example.com", "sentry", "wixpress", "noreply", "no-reply", "@2x", ".png", ".jpg")) \
        or e.split("@")[0] in ("info", "support", "contact", "hello", "admin", "help", "privacy", "press", "sales")


def _looks_like_date_or_id(s: str) -> bool:
    return bool(re.fullmatch(r"(?:19|20)\d{2}[\s.-]?\d{2}[\s.-]?\d{2,4}", s.strip()))
