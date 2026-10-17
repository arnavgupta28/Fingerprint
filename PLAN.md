# Fingerprint: build plan & pitch

## Phase 0: Before the event (or first hour)
- [ ] Repo skeleton ([FOLDER_STRUCTURE.md](FOLDER_STRUCTURE.md)), `.env.example`, Docker
- [ ] API keys: Claude, Brave Search, Exa, TinyFish, HIBP
- [ ] Pick the **demo persona**: a teammate who consents, with a deliberately public footprint
- [ ] Smudge SVG + logo in the app ([docs/DESIGN.md](docs/DESIGN.md))

## Phase 1: Before mentoring (to 3 PM)
Goal: **Light level works end to end, even if rough.**
- [ ] Input form with level picker + consent checkbox
- [ ] ① Plan → ② Search → ④ Extract on snippets only (skip fetch)
- [ ] Basic findings list with source links
- [ ] Architecture diagram + scope slide

## Phase 2: After mentoring (4–5 PM, 1 hour)
**Above the line (must finish):**
- [ ] Standard level: email → HIBP breaches; username probe on 5 platforms
- [ ] ③ Fetch with TinyFish for top hits
- [ ] ⑤ Match confidence + "Is this you?" buttons that re-score
- [ ] ⑥ Exposure score gauge + 🟢🟡🔴 labels + removal steps
- [ ] Masking of phone/address in UI and logs
- [ ] Live progress stream (Smudge "sniffing" each source)
- [ ] Mock mode with recorded fixtures

**── the line ──**

**Below the line (only if time):**
- [ ] Deep level: phone + employer disambiguation, people-finder checks
- [ ] Download report as PDF
- [ ] Circuit breaker demo toggle in the UI

## Mentoring pitch (3 minutes)

| Time | Say |
|---|---|
| 0:00–0:30 | **Hook:** "Raise your hand if you've had a scam call that knew your name and where you work. That info came from the public internet. Most people have no idea how much is out there." |
| 0:30–1:00 | **Problem:** Crumbs are scattered: old profiles, breaches, people-finder sites. Together they form a *fingerprint*. Checking manually takes hours, and you still don't know what to do. |
| 1:00–1:45 | **Solution:** Fingerprint. You pick how much to share: Light, Standard or Deep. We search the public web, show every finding with its source, score the risk, and give removal steps. Smudge guides you through. |
| 1:45–2:30 | **Design:** 6-step pipeline, cheap search first and agents only when needed, an "Is this you?" loop for namesakes. **Privacy by design:** self-search only, nothing stored, sensitive values masked. |
| 2:30–3:00 | **Plan + ask:** Show the Light-level scan working. "We'd love feedback on match accuracy and on abuse prevention." |

## Judging: 1-min pitch + 2-min demo

**Pitch (60 s):** "The internet remembers more about you than you do. Fingerprint shows you what's public about you, where it lives, how risky it is, and how to remove it. You choose how much to share, and we store none of it."

**Demo (120 s):**
1. **(15 s)** Open the app; Smudge greets. Pick **Standard**, enter the demo persona's name, city and email, tick consent.
2. **(35 s)** Live view: Smudge sniffs sources one by one; findings appear.
3. **(25 s)** Report: score **72 / 100**. Open a 🔴 item: phone on a people-finder, masked, with source link and evidence quote.
4. **(15 s)** Click **"Not me"** on a namesake; the score updates.
5. **(15 s)** Open removal steps for the breach finding.
6. **(15 s)** Reliability: turn off a source, rescan, and show the "couldn't check" badge and partial results. Mention mock mode, tests and `/health`.

## Likely Q&A: prepared answers

| Question | Answer |
|---|---|
| **Couldn't a stalker use this on someone else?** | Self-search consent, rate limits, no bulk mode, masked values in the output, and no storage. The report shows *where* data is, which a stalker could find by Googling anyway, but the value goes to the person it belongs to. Post-hackathon: email/phone verification so you can only run Standard or Deep on contact details you own. |
| **How do you handle people with the same name?** | Match confidence from overlapping fields + name rarity, and the "Is this you?" loop. More detail means fewer namesakes. |
| **Do you store my data?** | No. In-memory session with a 30-minute TTL; delete on close; PII-redacted logs. |
| **How do you stop the AI making things up?** | Strict JSON schema, and every data point must quote evidence from the page. No quote, no finding. |
| **Why TinyFish?** | Fetch is fast for plain pages; Agent handles JS-heavy pages that plain HTTP can't read. We use the Agent only when Fetch fails, to save cost. |
| **What does a scan cost?** | About 20 queries, 10 fetches and roughly 15k tokens, so cents per scan. A budget cap enforces it. |
| **Legal?** | Public pages only, robots.txt respected, no logins, short excerpts with links. Data minimisation aligns with the DPDP Act and GDPR. |
| **Business model?** | Free scan; paid monitoring (monthly re-scan + alerts) and assisted removal. B2B: employee exposure audits for security teams. |

## Risks

| Risk | Mitigation |
|---|---|
| Search API limits during demo | Fallback API + mock mode |
| Demo persona has too little online | Pre-check the night before; seed a public profile if needed |
| Wrong match shown on stage | Rehearse; "Not me" button is part of the story |
| Ethics question derails Q&A | Prepared answer above; guardrails slide ready |
