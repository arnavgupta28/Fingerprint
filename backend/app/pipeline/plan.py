"""① Plan: turn the user's details into targeted search queries. Deterministic, so free and repeatable.

Queries are ordered by how much they tell us: phone and email first (unique), then name + place, then
site-specific and corroborating searches. The budget cuts from the end."""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..models import COUNTRY_CODES, ScanFields

SOCIAL = "instagram.com,facebook.com,x.com,twitter.com,reddit.com,youtube.com,threads.net,pinterest.com"
PROFESSIONAL = "linkedin.com,naukri.com,wellfound.com,crunchbase.com"
CODE = "github.com,gitlab.com,stackoverflow.com,dev.to,medium.com,kaggle.com"
BROKERS = "truecaller.com,justdial.com,spokeo.com,whitepages.com,radaris.com,peekyou.com,nuwber.com,thatsthem.com,contactout.com,rocketreach.co"
DOCS = "scribd.com,slideshare.net,issuu.com,academia.edu,researchgate.net"


@dataclass(frozen=True)
class Query:
    text: str
    purpose: str
    include_domains: str | None = None


def build_queries(f: ScanFields, level: str, max_queries: int) -> list[Query]:
    name = f'"{f.full_name}"'
    city = f" {f.city}"
    variants = phone_variants(f.phone_local, COUNTRY_CODES.get(f.country, ""))

    q: list[Query] = [Query(f'"{v}"', f"Pages that show your phone number (format {i}/{len(variants)})")
                      for i, v in enumerate(variants, 1)]
    q += [Query(f'"{f.phone_local}"', "Your phone on people-finder sites", BROKERS)]
    if f.email:
        q += [Query(f'"{f.email}"', "Pages that show your email address")]
    q += [
        Query(f"{name}{city}", "Your name and city"),
        Query(f"{name}{city}", "People-finder and directory sites", BROKERS),
        Query(f"{name}{city}", "Professional profiles", PROFESSIONAL),
        Query(f"{name}{city}", "Social media profiles", SOCIAL),
        Query(name, "Anything indexed under your exact name"),
        Query(f"{name}{city} address", "Pages listing an address"),
        Query(f"{name} resume CV", "Résumés and CVs"),
        Query(name, "Public documents", DOCS),
    ]
    for u in f.usernames:
        q += [
            Query(f'"{u}"', f"Your username “{u}” across the web"),
            Query(f'"{u}"', f"“{u}” on code and dev sites", CODE),
            Query(f'"{u}"', f"“{u}” on social sites", SOCIAL),
        ]
    if f.email:
        local = f.email.split("@")[0]
        if len(local) >= 5 and local not in f.usernames:
            q += [Query(f'"{local}"', "Your email handle reused as a username")]
    if f.birth_year:
        q += [Query(f"{name} {f.birth_year}", "Pages that mention your birth year")]
    for n in f.names[1:]:
        q += [Query(f'"{n}"{city}', f"Your other name “{n}”")]
    if f.employer:
        q += [Query(f'{name} "{f.employer}"', "You and your workplace")]
    if f.school:
        q += [Query(f'{name} "{f.school}"', "You and your school or college")]
    for past in f.past_cities:
        q += [Query(f"{name} {past}", f"You and a past city ({past})")]

    seen, unique = set(), []
    for item in q:
        key = (item.text.lower(), item.include_domains)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique[:max_queries]


def phone_variants(local: str, cc: str = "") -> list[str]:
    """Common ways a number is written: 9876543210, 98765 43210, 987-654-3210, +91 98765 43210."""
    d = re.sub(r"\D", "", local)
    out = [d]
    if len(d) == 10:
        out += [f"{d[:5]} {d[5:]}", f"{d[:3]}-{d[3:6]}-{d[6:]}"]
        if cc:
            out.append(f"+{cc} {d[:5]} {d[5:]}")
    return out
