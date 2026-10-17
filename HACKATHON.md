# Hackathon Brief: Fingerprint @ Ignite Room

One page with everything about the event: rounds, timings, how we're judged, and the rules we follow.

> ✅ = confirmed from the official evaluation slide · ❓ = not yet confirmed; ask the organisers

---

## 1. Event at a glance

| Item | Detail |
|---|---|
| Event | **Ignite Room** hackathon ✅ |
| Our project | **Fingerprint**: enter as much or as little about yourself as you like; we search the public web and show what's exposed, where, how risky it is, and how to remove it ([aim.md](aim.md)) |
| Mascot | **Smudge**, a friendly fingerprint with a magnifying glass ([docs/DESIGN.md](docs/DESIGN.md)) |
| Key tech | Search APIs, TinyFish (web agents), Claude (AI), Have I Been Pwned (breaches) ([ARCHITECTURE.md](ARCHITECTURE.md)) |
| Team size | ❓ |
| Submission format (repo link / deployed URL / video) | ❓ |
| Final code freeze time | ❓ (assume **before 5:00 PM**) |
| Required or sponsor tools (e.g. must use TinyFish?) | ❓ |
| Prizes / tracks | ❓ |

## 2. Rounds & timings ✅

| | **Mentoring Round** | **Judging Round** |
|---|---|---|
| **Time** | 3:00 – 4:00 PM | 5:00 – 6:00 PM |
| **Format** | 3 min pitch + 2 min Q&A | 1 min pitch + 2 min project demo + 2 min Q&A |
| **Total per team** | 5 min | 5 min |
| **What to show** | Problem, design, plan, early working pipeline | A complete, working, reliable product |
| **Our script** | [PLAN.md → Mentoring pitch](PLAN.md#mentoring-pitch-3-minutes) | [PLAN.md → Judging](PLAN.md#judging-1-min-pitch--2-min-demo) |

**Time limits are strict:** rehearse with a timer. Going over likely cuts into Q&A, or stops the pitch mid-way.

## 3. Evaluation criteria ✅

Each criterion is scored **out of 5**, giving **25 points per round**.

### Mentoring Round (25)

| # | Criterion | What judges look for | How we answer it | Proof to show |
|---|---|---|---|---|
| 1 | **Problem Clarity** (5) | A real, specific problem for a clear user | People don't know what's public about them; scattered crumbs add up to a fingerprint that enables scams and stalking | [aim.md §1](aim.md#1-the-problem) |
| 2 | **Design Decisions** (5) | Choices with reasons and trade-offs | User-chosen detail levels; "Is this you?" loop; self-search only; masked output; nothing stored; cheap search first, agents only when needed | [ARCHITECTURE.md §6](ARCHITECTURE.md#6-design-decisions) |
| 3 | **Scalability** (5) | Will it grow without breaking or costing a fortune? | Stateless scans; parallel source workers; per-query caching; budget cap per scan; new source = one YAML entry | [ARCHITECTURE.md §7](ARCHITECTURE.md#7-scalability) |
| 4 | **Technical Implementation** (5) | Is it actually built, and built well? | 6-step pipeline: plan → search → fetch → extract → match → score, with schema-validated JSON and a source on every finding | Live scan in the app |
| 5 | **Scope & Prioritisation** (5) | Realistic must / should / won't | Must: 3 levels, live search, confirm loop, score, removal steps. Won't: searching others, dark web, storing data | [aim.md §7](aim.md#7-scope-for-the-hackathon) |

### Judging Round (25)

| # | Criterion | What judges look for | How we answer it | Proof to show |
|---|---|---|---|---|
| 1 | **Production Standards** (5) | Code quality, config, tests, logging, security | Typed code, env config, **PII-redacted logs**, tests on fixtures, `/health`, Docker, no secrets in code | Terminal: `pytest` passing, `/health` green |
| 2 | **Technical Understanding** (5) | Can the team explain how and why? | Everyone can explain query planning, entity matching / confidence, masking, why nothing is stored | [PLAN.md Q&A](PLAN.md#likely-qa-prepared-answers) |
| 3 | **System Architecture** (5) | Clean, sensible structure | Input → planner → search → fetch → extract → match & score → report, with a guardrail layer; Live / Mock modes | [docs/architecture.svg](docs/architecture.svg) |
| 4 | **Completeness** (5) | Does the core flow work end to end? | Pick level → enter details → live scan → confirm findings → score → removal steps | Demo |
| 5 | **Reliability** (5) | Does it hold up when things fail? | Timeouts + retries, per-source circuit breaker, search API fallback, per-scan budget cap, partial results, mock replay | Turn a source off live in the demo |

## 4. Rules we abide by

### From the event ✅
- Stay inside the **time limits** for each round (Section 2).
- Be present for **both rounds** at the scheduled times.

### To confirm with organisers ❓
- [ ] Can we use code written **before** the event, or must everything be built during it?
- [ ] Are **open-source libraries, templates and AI coding tools** allowed?
- [ ] Is a **deployed URL** required, or is a local demo fine?
- [ ] What do we submit, where, and by when?
- [ ] Any required sponsor tech (e.g. TinyFish) or restricted tech?
- [ ] Team size limits; can mentors' feedback be applied between rounds? (We plan to.)

### Our own rules: product, legal & ethics
| Rule | Why |
|---|---|
| **Self-search only**: consent checkbox before every scan; no "search someone else" mode | Stops the tool being used for stalking or doxxing |
| **Nothing stored server-side**: session in memory, deleted on close or after 30 min | Privacy by design; aligns with DPDP Act / GDPR data minimisation |
| **Mask sensitive values** (phone, address, ID numbers) in the UI and logs | The report itself must not become a leak |
| **Public pages only**: never log in, bypass paywalls, or buy data | Legal and ToS-safe |
| **Polite fetching**: low request rates, caching, honest User-Agent, respect robots.txt | Don't overload sites; avoid getting blocked |
| **Every finding links to its source**; show confidence, never state guesses as facts | Trust, and a defence against wrong matches |
| **Demo with a consenting teammate or a fictional persona** in mock mode; label mock data | Never expose a real third party on stage |
| **Secrets in env vars only**; nothing committed | Production standards |

## 5. Day-of checklist

**Before 3:00 PM (Mentoring)**
- [ ] 3-min pitch rehearsed twice with a timer
- [ ] Architecture diagram + scope slide ready
- [ ] At least one level (Light) → one real finding working end to end (even if rough)
- [ ] Notes ready to capture mentor feedback

**4:00 – 5:00 PM (Build)**
- [ ] Apply the top 1–2 pieces of mentor feedback
- [ ] Finish everything above "the line" in [PLAN.md Phase 2](PLAN.md#phase-2-after-mentoring-45-pm-1-hour)
- [ ] Record fixtures for the demo persona → mock replay works offline

**Before 5:00 PM (Judging)**
- [ ] 1-min pitch + 2-min demo rehearsed **3 times** (once in mock mode)
- [ ] Tabs open: app, architecture SVG, terminal with tests + logs
- [ ] Demo persona agreed (who is being scanned, with their consent)
- [ ] API keys loaded; budget cap set
- [ ] Backup: mock mode + screen recording of a full run

## 6. Related docs

| Doc | What's in it |
|---|---|
| [aim.md](aim.md) | What we're building, in plain English |
| [PLAN.md](PLAN.md) | Build phases, pitch scripts, Q&A, risks |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Full system design |
| [SOURCES.md](SOURCES.md) | Where we search, and how to add a source |
| [docs/DESIGN.md](docs/DESIGN.md) | Look & feel, Smudge the mascot, animations |
| [FOLDER_STRUCTURE.md](FOLDER_STRUCTURE.md) | Repo layout |
