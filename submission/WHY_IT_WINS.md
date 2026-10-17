# Why Fingerprint stands out

Each judging criterion, the claim we make, and where to check it. Every claim below points to code in this repository.

## Summary

- **A real, everyday problem.** Scattered public data enables scams, doxxing and stalking, and most people can't see their own exposure.
- **A complete, working product.** Choose a level, scan live, see findings stream in, tap "Is this you?", get a score, and follow the removal steps.
- **TinyFish is central.** Search, Fetch and Agent are each used for what they do best, with cost-aware escalation between them ([TINYFISH.md](TINYFISH.md)).
- **Privacy by design.** Self-search consent is enforced by the API, nothing is stored, output is masked, logs are redacted, and no personal data is sent to an LLM.
- **Built to keep working when things fail.** Per-product circuit breakers, retries, budget caps, and partial results instead of crashes.

---

## Mentoring round

| Criterion | Our answer | Proof |
|---|---|---|
| **Problem clarity** | One specific user (a person checking themselves) and one specific harm (combined public crumbs → scams, stalking, impersonation) | [PITCH.md §1](PITCH.md#1-the-real-world-problem) |
| **Design decisions** | User-chosen detail level; "Is this you?" loop for namesakes; masked output; nothing stored; Search → Fetch → Agent escalation; rule-based extraction so no personal data goes to an LLM and nothing is hallucinated | [`models.py` `LEVEL_FIELDS`](../backend/app/models.py), [`runner.py` `read_pages` / `try_agent`](../backend/app/pipeline/runner.py), [`extract.py`](../backend/app/pipeline/extract.py) |
| **Scalability** | Stateless scans; parallel searches and fetch batches; per-scan budget caps; new platforms, domains and playbooks are a **YAML entry, not a code change** | [`config.yaml`](../config.yaml), [`config/sources.yaml`](../config/sources.yaml), [`config/playbooks.yaml`](../config/playbooks.yaml) |
| **Technical implementation** | Six-stage async pipeline (plan → search → fetch → extract → match → score) streamed live over SSE | [`pipeline/`](../backend/app/pipeline/), [`main.py`](../backend/app/main.py) |
| **Scope & prioritisation** | Must-haves shipped (3 levels, live search, confirm loop, score, removal steps). We deliberately **won't** search for other people, monitor the dark web, or store data | [../aim.md §7](../aim.md#7-scope-for-the-hackathon) |

## Judging round

| Criterion | Our answer | Proof |
|---|---|---|
| **Production standards** | Typed Pydantic models with validation; config in YAML with env overrides; secrets only in `.env`; **PII-redacting log filter**; per-IP rate limit; `/health`; **18 passing tests** | [`guardrails.py`](../backend/app/guardrails.py), [`backend/tests/`](../backend/tests/), `pytest -q` |
| **Technical understanding** | We can explain query planning, the weighted match-confidence model (a name alone is capped at 0.35 because many people share names), risk = sensitivity × confidence, the exposure score `100·(1−e^(−Σ/40))`, and why the Agent runs only on blocked broker pages | [`match.py`](../backend/app/pipeline/match.py), [`score.py`](../backend/app/pipeline/score.py) |
| **System architecture** | Clear layers: API → session store → pipeline → TinyFish client and probes, with a guardrail layer around them. Each stage is its own module with one job | [../docs/architecture.svg](../docs/architecture.svg), [../ARCHITECTURE.md](../ARCHITECTURE.md) |
| **Completeness** | The full flow works end to end in the browser: level → details + consent → live scan → findings → verdicts → re-score → removal steps → delete session | [`frontend/`](../frontend/), [`main.py` routes](../backend/app/main.py) |
| **Reliability** | Retries with backoff and `Retry-After`; **a circuit breaker per TinyFish product**; Fetch failure → snippet fallback; per-source "couldn't check" status; budget cap → `partial: true` instead of an error | [`tinyfish.py`](../backend/app/tinyfish.py), [`runner.py` `fetch_batch`](../backend/app/pipeline/runner.py) |

## Details judges tend to ask about

- **"Could a stalker use this?"** The API rejects any scan without `consent: true`. There is no bulk mode, scans are limited to 10 per hour per IP, and output is masked (`98•••••210`, `a•••@gmail.com`), so the report shows *where* data is, not the raw values. Next step: verifying ownership of the email or phone with an OTP before Standard or Deep scans.
- **"How do you avoid false positives?"** Every finding needs a quote from the page that sits near your name or identifiers. Confidence comes from overlapping fields, with weighted reasons shown to the user. Detailed data points are only extracted from pages scoring at least 0.3, and "Not me" removes the whole page and recalculates the score.
- **"Do you store anything?"** No. Sessions are kept in memory with a 30-minute TTL, `DELETE /api/scan/{id}` removes one immediately, raw values never leave the server, and logs pass through a PII redactor.
- **"Is it legal and ethical?"** Public pages only. We never log in, bypass paywalls or buy data; login-walled sites are snippet-only; the Agent is told to stop at any login or captcha; and we send an honest User-Agent. This is in line with DPDP and GDPR data minimisation.
- **"What does it cost to run?"** About $0 per default scan on TinyFish's free Search and Fetch allowance. The Agent is opt-in at $0.016 per step with a per-scan cap, and the cost is reported on every scan.

## In one line

> **Fingerprint turns the attacker's first step, collecting public crumbs, into a tool that protects the person being targeted. TinyFish powers the scanning, and the privacy protections are enforced in code.**
