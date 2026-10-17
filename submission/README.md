# Fingerprint: submission

<p align="center"><img src="../assets/mascot/smudge.svg" width="140" alt="Smudge, the Fingerprint mascot"></p>

> **See what the internet knows about you, before someone else does.**

Fingerprint is a self-scan for your digital footprint. You enter as much or as little about yourself as you like. It searches the live public web with **TinyFish**, reads the pages that mention you, and returns a report: what is exposed, where it is (with the source link and a quoted line from the page), how risky each item is, and step-by-step instructions for removing it. Nothing is stored, and sensitive values are masked so the report can't be used to dox you.

## Read in this order

| # | File | What it answers | Read time |
|---|---|---|---|
| 1 | [PITCH.md](PITCH.md) | What we built, the real problem, who it's for, why it's new | 3 min |
| 2 | [TINYFISH.md](TINYFISH.md) | Why TinyFish is the core of the system and how each part of it is used | 3 min |
| 3 | [WHY_IT_WINS.md](WHY_IT_WINS.md) | Each judging criterion matched to proof in the code | 4 min |

## Facts at a glance

| | |
|---|---|
| **What** | A live digital-footprint scanner with a removal guide for every finding |
| **For** | Everyday people, people at higher risk (journalists, creators, harassment survivors), and job seekers |
| **Core engine** | TinyFish **Search** → TinyFish **Fetch** → TinyFish **Agent** (opt-in fallback) |
| **Pipeline** | Plan → Search → Fetch → Extract → Match → Score, streamed live to the user |
| **Privacy** | Self-search only (consent is enforced by the API), in-memory sessions with a 30-minute TTL, masked output, PII-redacted logs, and no personal data sent to an LLM |
| **Reliability** | Retries with backoff, a circuit breaker per TinyFish product, per-scan budget caps, partial results with a "couldn't check" status per source |
| **Cost per scan** | About $0 by default: Search and Fetch use TinyFish's free daily allowance, and the paid Agent is opt-in and capped |
| **Quality** | Typed FastAPI + Pydantic backend, YAML-driven sources and playbooks, `/health` endpoint, 18 passing tests |

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install fastapi uvicorn httpx pydantic pyyaml python-dotenv pytest pytest-asyncio
echo "TINYFISH_API_KEY=..." > .env
uvicorn backend.app.main:app --reload    # open http://localhost:8000
pytest -q                                # 18 passed
```
