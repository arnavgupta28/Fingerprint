from datetime import date

import pytest
from pydantic import ValidationError

from backend.app.guardrails import RateLimiter, mask, redact
from backend.app.models import Finding, Removal, ScanFields, ScanRequest
from backend.app.pipeline.extract import extract, name_anchors
from backend.app.pipeline.match import confidence_label, page_confidence, page_match
from backend.app.pipeline.plan import build_queries, phone_variants
from backend.app.pipeline.score import rescore, risk_for

AGE = date.today().year - 1996
F = ScanFields(full_name="Asha Rao", city="Pune", country="IN", phone="+91 98765 43210",
               email="asha.rao@mail.test", usernames=["asharao_dev"], employer="Nimbus Labs", birth_year=1996)
REQ = {"full_name": "Asha Rao", "phone": "9876543210", "city": "Pune"}


# ── guardrails ──────────────────────────────────────────────────────────────
def test_masking_hides_most_of_the_value():
    assert mask("phone", "919876543210") == "91•••••••210"
    assert mask("email", "asha.rao@mail.test") == "a•••@mail.test"
    assert "Kothrud" not in mask("address", "Flat 12, Shanti Nagar, Kothrud 411038")


def test_redact_masks_emails_and_phones_in_free_text():
    out = redact("Call +91 98765 43210 or mail asha.rao@mail.test")
    assert "98765 43210" not in out and "asha.rao@" not in out


def test_rate_limiter_blocks_after_limit():
    rl = RateLimiter(limit=2)
    assert rl.allow("ip") and rl.allow("ip") and not rl.allow("ip")


# ── models: required vs optional ────────────────────────────────────────────
@pytest.mark.parametrize("missing", ["full_name", "phone", "city"])
def test_name_phone_city_are_required(missing):
    fields = {k: v for k, v in REQ.items() if k != missing}
    with pytest.raises(ValidationError):
        ScanRequest(level="light", consent=True, fields=fields)


def test_consent_is_required():
    with pytest.raises(ValidationError):
        ScanRequest(level="light", consent=False, fields=REQ)


def test_level_drops_optional_fields_it_does_not_allow():
    r = ScanRequest(level="light", consent=True, fields={**REQ, "email": "a@b.co", "birth_year": 1990,
                                                          "usernames": ["x_y"], "employer": "Acme"})
    assert r.fields.email is None and r.fields.birth_year is None and r.fields.usernames == [] and r.fields.employer is None
    r = ScanRequest(level="standard", consent=True, fields={**REQ, "email": "a@b.co", "employer": "Acme"})
    assert r.fields.email == "a@b.co" and r.fields.employer is None


def test_phone_local_strips_country_code():
    assert ScanFields(**{**REQ, "phone": "+91 98765 43210"}).phone_local == "9876543210"
    assert ScanFields(**{**REQ, "phone": "09876543210"}).phone_local == "9876543210"


@pytest.mark.parametrize("bad", [{"birth_year": 1800}, {"phone": "123"}, {"full_name": "Asha"},
                                 {"aliases": ["Asha"]}, {"country": "ZZ"}])
def test_invalid_inputs(bad):
    with pytest.raises(ValidationError):
        ScanFields(**{**REQ, **bad})


def test_names_include_middle_and_aliases():
    f = ScanFields(**REQ, middle_name="Kiran", aliases=["Asha Sharma"])
    assert f.names == ["Asha Rao", "Asha Kiran Rao", "Asha Sharma"]


# ── plan ────────────────────────────────────────────────────────────────────
def test_phone_is_searched_first_at_every_level():
    r = ScanRequest(level="light", consent=True, fields=F.model_dump())
    qs = build_queries(r.fields, "light", 50)
    assert qs[0].text == '"9876543210"'
    assert "mail.test" not in " ".join(q.text for q in qs)


def test_plan_respects_budget():
    assert len(build_queries(F, "deep", 5)) == 5


def test_phone_variants():
    assert phone_variants("9876543210", "91") == ["9876543210", "98765 43210", "987-654-3210", "+91 98765 43210"]


# ── extract ─────────────────────────────────────────────────────────────────
PAGE = """Header stuff. Call our office 080-4000-1234 for support at info@site.test.
""" + ("filler text. " * 80) + """
Asha Rao, 29 years old, lives in Kothrud. Mobile: +91 98765 43210. Email: asha.rao@mail.test.
Address: Flat 12, Shanti Nagar Road, Kothrud, Pune 411038. Works at Nimbus Labs.
Studied at Deccan Institute of Technology. Relatives: Ravi Rao."""


def test_extract_finds_details_near_the_name_only():
    points = {(p.type, p.value) for p in extract(PAGE, F)}
    types = {t for t, _ in points}
    assert {"phone", "email", "address", "age", "employer", "education", "family"} <= types
    assert ("phone", "919876543210") in points
    assert not any(v.endswith("1234") for t, v in points if t == "phone"), "site-wide number far from the name"
    assert ("email", "info@site.test") not in points


def test_extract_ignores_pages_without_the_person():
    assert extract("Some page about Ravi Kumar, phone 9876500000", F) == []


def test_extract_uses_aliases():
    f = ScanFields(**REQ, aliases=["Asha Sharma"])
    assert any(p.type == "employer" for p in extract("Asha Sharma works at Orbit Systems.", f))


def test_name_anchor_variants():
    assert name_anchors("Rao, Asha — designer", "Asha Rao")
    assert name_anchors("Asha K. Rao", "Asha Rao")


def test_toll_free_numbers_and_junk_words_are_ignored():
    text = "Book Asha Rao: call 1-800-555-0199. Works at Jul. Lives in Pune and Mumbai."
    points = {(p.type, p.value) for p in extract(text, F)}
    assert not any(t == "phone" for t, _ in points)
    assert not any(t == "employer" for t, _ in points)


# ── match ───────────────────────────────────────────────────────────────────
def test_name_alone_is_weak_evidence():
    m = page_match("Asha Rao is a nurse", "https://x.test", F)
    assert m.reasons == ["full name"] and m.confidence <= 0.35


def test_name_plus_one_detail_is_capped():
    m = page_match("Asha Rao, Pune", "https://x.test", F)
    assert set(m.reasons) == {"full name", "city"} and m.confidence <= 0.6


def test_phone_makes_it_very_likely():
    m = page_match("Asha Rao · 98765 43210", "https://x.test", F)
    assert "phone" in m.reasons and m.confidence >= 0.75
    assert confidence_label(m.confidence) == "Very likely you"


def test_age_that_fits_birth_year_raises_confidence():
    fits = page_match(f"Asha Rao, age {AGE}, Pune", "https://x.test", F)
    contradicts = page_match("Asha Rao, age 61, Pune", "https://x.test", F)
    assert "age" in fits.reasons and "age doesn't match" in contradicts.mismatches
    assert fits.confidence > contradicts.confidence


def test_middle_initial_conflict_counts_against():
    f = ScanFields(**REQ, middle_name="Kiran")
    assert "different middle initial" in page_match("Asha M. Rao from Pune", "https://x.test", f).mismatches
    assert "middle name" in page_match("Asha K. Rao from Pune", "https://x.test", f).reasons


def test_username_that_is_part_of_the_name_needs_a_handle_match():
    f = ScanFields(full_name="Linus Torvalds", phone="5035550100", city="Portland", country="US", usernames=["torvalds"])
    _, reasons = page_confidence("An article about Linus Torvalds", "https://news.test/a", f)
    assert "username" not in reasons
    _, reasons = page_confidence("Linus Torvalds", "https://github.com/torvalds", f)
    assert "username" in reasons


def test_profile_vs_post_urls():
    from backend.app.pipeline.runner import is_profile_url
    assert is_profile_url("https://www.linkedin.com/in/asha-rao")
    assert is_profile_url("https://x.com/asharao")
    assert not is_profile_url("https://x.com/asharao/status/123")
    assert not is_profile_url("https://www.linkedin.com/posts/someone_asha-rao-activity-1")


# ── score ───────────────────────────────────────────────────────────────────
def test_risk_mapping():
    assert risk_for("high", 0.8) == "red"
    assert risk_for("high", 0.4) == "red"
    assert risk_for("high", 0.35) == "amber"
    assert risk_for("low", 0.99) == "green"


def test_not_me_removes_finding_from_score():
    f = Finding(id="f1", category="contact", type="phone", label="Phone", value_masked="98•••210", source_url="u",
                source_name="s", evidence="", confidence=0.9, sensitivity="high", risk="red",
                removal=Removal(playbook="generic", title="t", steps=[]))
    before, _, _ = rescore([f])
    f.user_verdict = "not_me"
    after, _, counts = rescore([f])
    assert before > 0 and after == 0 and counts["red"] == 0


def test_phone_only_page_keeps_only_your_number():
    text = "Numbers: 98765 43210, 98765 43211, 98765 43212 — reverse lookup"
    assert {(p.type, p.value) for p in extract(text, F)} == {("phone", "9876543210")}


def test_phone_directory_pages_are_penalised():
    nums = ", ".join(f"98765 4{i:04d}" for i in range(3200, 3215))
    m = page_match(f"Lookup {nums}", "https://dir.test", F)
    assert "phone" in m.reasons and "page lists many people's numbers" in m.mismatches
    assert m.confidence < page_match("Call 98765 43210", "https://x.test", F).confidence


def test_without_your_name_it_is_never_very_likely():
    m = page_match("Call 98765 43210 — our office in Pune", "https://shop.test", F)
    assert "phone" in m.reasons and m.confidence <= 0.7


@pytest.mark.parametrize("raw", ["9896830, Innovation Group", "call 989-683-05...", "+91 98968 30917", "PIN 560001"])
def test_redact_masks_partial_and_hyphenated_numbers(raw):
    out = redact(raw)
    assert "9896830" not in out.replace("-", "").replace(" ", "")
    assert "989-683" not in out and "560001" not in out


def test_redact_keeps_years_and_short_numbers():
    assert redact("Founded in 2019, 42 people") == "Founded in 2019, 42 people"


def test_redacted_fragments_reveal_no_digits():
    assert redact("9896830, Innovation Group") == "•••••••, Innovation Group"
