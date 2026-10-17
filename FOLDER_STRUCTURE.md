# Fingerprint: folder structure

```
Fingerprint/
├── aim.md                  # What & why (plain English)
├── HACKATHON.md            # Event brief, judging, rules
├── PLAN.md                 # Build phases, pitch, Q&A
├── ARCHITECTURE.md         # System design
├── SOURCES.md              # Where we search + removal playbooks
├── FOLDER_STRUCTURE.md     # This file
├── .env.example            # API keys template (never commit .env)
├── docker-compose.yml
│
├── assets/
│   ├── mascot/smudge.svg   # Smudge the mascot
│   └── logo/icon.svg       # App icon / favicon
│
├── docs/
│   ├── DESIGN.md           # Look & feel, mascot, animations
│   └── architecture.svg    # Pipeline diagram
│
├── config/
│   ├── sources.yaml        # Source definitions
│   └── playbooks.yaml      # Removal steps per finding type
│
├── backend/
│   ├── app/
│   │   ├── main.py         # FastAPI app, routes, /health
│   │   ├── models.py       # Pydantic: ScanRequest, Finding, Report
│   │   ├── session.py      # In-memory store with TTL
│   │   ├── guardrails.py   # Consent, rate limits, masking, PII log filter
│   │   └── pipeline/
│   │       ├── plan.py     # ① queries from inputs
│   │       ├── search.py   # ② search APIs, HIBP, username probe
│   │       ├── fetch.py    # ③ TinyFish Fetch → Agent fallback
│   │       ├── extract.py  # ④ Claude → schema JSON + evidence
│   │       ├── match.py    # ⑤ confidence / namesake handling
│   │       └── score.py    # ⑥ risk, exposure score, playbooks
│   └── tests/
│       ├── fixtures/       # Recorded pages for mock mode + tests
│       └── test_*.py
│
└── frontend/
    ├── app/                # Next.js pages: home, scan, report
    ├── components/         # LevelPicker, LiveFeed, FindingCard, ScoreGauge, Smudge
    └── public/             # Copies of assets/
```
