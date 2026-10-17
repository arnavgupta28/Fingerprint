"""API and pipeline data models."""
from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Level = Literal["light", "standard", "deep"]
Category = Literal[
    "identity", "contact", "location", "work", "education", "social", "code", "media", "family", "breach", "broker"
]
Sensitivity = Literal["low", "medium", "high"]
Risk = Literal["green", "amber", "red"]
Verdict = Literal["me", "not_me"]

# Required for every scan: the minimum that lets us tell you apart from namesakes (see docs/INPUT-FIELDS.md).
REQUIRED_FIELDS = {"full_name", "phone", "city", "country"}
# Optional fields each level unlocks. Anything else is dropped server-side.
LEVEL_FIELDS: dict[str, set[str]] = {
    "light": REQUIRED_FIELDS,
    "standard": REQUIRED_FIELDS | {"birth_year", "email", "usernames", "state"},
    "deep": REQUIRED_FIELDS | {"birth_year", "email", "usernames", "state", "middle_name", "aliases", "employer",
                               "school", "past_cities"},
}
COUNTRY_CODES = {"IN": "91", "US": "1", "GB": "44", "CA": "1", "AU": "61", "DE": "49", "FR": "33", "SG": "65", "AE": "971"}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{2,40}$")
NAME_RE = re.compile(r"^[^\d@#$%^*_=+<>{}\[\]|\\/]{2,80}$")


class ScanFields(BaseModel):
    # required
    full_name: str = Field(min_length=3, max_length=80)
    phone: str = Field(max_length=20)
    city: str = Field(min_length=2, max_length=60)
    country: str = Field(default="IN", min_length=2, max_length=2)
    # optional
    birth_year: int | None = Field(default=None)
    email: str | None = Field(default=None, max_length=120)
    usernames: list[str] = Field(default_factory=list, max_length=3)
    state: str | None = Field(default=None, max_length=60)
    middle_name: str | None = Field(default=None, max_length=40)
    aliases: list[str] = Field(default_factory=list, max_length=3)
    employer: str | None = Field(default=None, max_length=80)
    school: str | None = Field(default=None, max_length=100)
    past_cities: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("*", mode="before")
    @classmethod
    def _strip(cls, v):
        if isinstance(v, str):
            v = " ".join(v.split())
            return v or None
        if isinstance(v, list):
            return [" ".join(x.split()) for x in v if isinstance(x, str) and x.strip()]
        return v

    @field_validator("full_name")
    @classmethod
    def _full_name(cls, v: str) -> str:
        if len(v.split()) < 2 or not NAME_RE.match(v):
            raise ValueError("enter your first and last name")
        return v

    @field_validator("aliases")
    @classmethod
    def _aliases(cls, v: list[str]) -> list[str]:
        for a in v:
            if len(a.split()) < 2 or not NAME_RE.match(a):
                raise ValueError("other names need a first and last name, e.g. a maiden name")
        return v

    @field_validator("country")
    @classmethod
    def _country(cls, v: str) -> str:
        v = v.upper()
        if v not in COUNTRY_CODES:
            raise ValueError("unsupported country")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v or "")
        if not 8 <= len(digits) <= 15:
            raise ValueError("enter a valid phone number")
        return digits

    @field_validator("birth_year")
    @classmethod
    def _birth_year(cls, v):
        if v is not None and not 1920 <= v <= date.today().year - 13:
            raise ValueError("birth year must be between 1920 and 13 years ago")
        return v

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        if v and not EMAIL_RE.match(v):
            raise ValueError("invalid email")
        return v.lower() if v else v

    @field_validator("usernames")
    @classmethod
    def _usernames(cls, v: list[str]) -> list[str]:
        out = []
        for u in v:
            u = u.lstrip("@")
            if not USERNAME_RE.match(u):
                raise ValueError("usernames can use letters, numbers, dot, dash and underscore")
            out.append(u)
        return list(dict.fromkeys(out))

    # ── helpers used by the pipeline ──
    @property
    def phone_local(self) -> str:
        """National number without the country code: the part people actually write on web pages."""
        cc = COUNTRY_CODES.get(self.country, "")
        d = self.phone
        if cc and d.startswith(cc) and len(d) - len(cc) >= 8:
            d = d[len(cc):]
        return d.lstrip("0")

    @property
    def names(self) -> list[str]:
        """Every name you might appear under: full name, with middle name, and aliases."""
        out = [self.full_name]
        if self.middle_name:
            parts = self.full_name.split()
            out.append(" ".join([parts[0], self.middle_name, *parts[1:]]))
        return list(dict.fromkeys(out + self.aliases))

    @property
    def age_range(self) -> tuple[int, int] | None:
        if not self.birth_year:
            return None
        age = date.today().year - self.birth_year
        return age - 1, age


class ScanRequest(BaseModel):
    level: Level
    fields: ScanFields
    consent: bool

    @model_validator(mode="after")
    def _consent_and_scope(self):
        if self.consent is not True:
            raise ValueError("You must confirm you are searching for yourself.")
        allowed = LEVEL_FIELDS[self.level]
        for name, info in ScanFields.model_fields.items():
            if name not in allowed:
                setattr(self.fields, name, info.default_factory() if info.default_factory else info.default)
        return self


class Removal(BaseModel):
    playbook: str
    title: str
    steps: list[str]


class Finding(BaseModel):
    id: str
    category: Category
    type: str                       # phone, email, address, employer, profile, breach, mention, ...
    label: str                      # human-readable title
    value_masked: str               # raw value never leaves the server
    source_url: str
    source_name: str
    source_title: str = ""
    evidence: str                   # short masked quote from the page
    confidence: float
    confidence_label: str = ""      # "Very likely you" … "Probably not you"
    sensitivity: Sensitivity
    risk: Risk
    matches_input: bool = False     # the value equals something the user typed
    match_reasons: list[str] = Field(default_factory=list)       # signals that point to you
    mismatch_reasons: list[str] = Field(default_factory=list)    # signals that point to someone else
    removal: Removal
    user_verdict: Verdict | None = None


class SourceStatus(BaseModel):
    name: str
    kind: str                       # search | fetch | probe | breach | agent
    status: Literal["ok", "failed", "blocked", "skipped"]
    detail: str = ""


class Report(BaseModel):
    scan_id: str
    level: Level
    status: Literal["running", "done", "failed"]
    score: int = 0
    score_label: str = "Low"
    summary: str = ""
    counts: dict[str, int] = Field(default_factory=lambda: {"red": 0, "amber": 0, "green": 0})
    findings: list[Finding] = Field(default_factory=list)
    sources: list[SourceStatus] = Field(default_factory=list)
    partial: bool = False
    cost_usd: float = 0.0
    started_at: str
    finished_at: str | None = None


class VerdictRequest(BaseModel):
    finding_id: str
    verdict: Verdict
