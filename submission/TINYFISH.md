# TinyFish: the core of Fingerprint

**Fingerprint is a TinyFish application.** All web discovery and all page reading go through TinyFish. Without it, no scan happens: the `/health` endpoint reports the TinyFish key and breaker states first, and the app refuses to start without `TINYFISH_API_KEY`.

Client: [`backend/app/tinyfish.py`](../backend/app/tinyfish.py) · Orchestration: [`backend/app/pipeline/runner.py`](../backend/app/pipeline/runner.py)

---

## 1. The three TinyFish products and what each one does for us

```
        user details (Light / Standard / Deep)
                       │
                       ▼
   ① Plan  ── up to 24 targeted queries, each with a purpose
                       │
                       ▼
 ┌──────────────── TinyFish Search ────────────────┐   finds WHERE you are exposed
 │ geo-targeted (location=IN), domain-scoped        │   free daily allowance
 │ include_domains = brokers / social / code / docs │   5 searches in parallel
 └──────────────────────────────────────────────────┘
                       │ snippets scored for "is this you?"
                       ▼
 ┌──────────────── TinyFish Fetch ─────────────────┐   reads WHAT the page says
 │ up to 10 URLs per call, returned as markdown     │   free daily allowance
 │ structured errors: login_required, bot_blocked   │   batches run in parallel
 └──────────────────────────────────────────────────┘
                       │ only if a people-finder blocked the fetch
                       ▼
 ┌──────────────── TinyFish Agent ─────────────────┐   gets past JS and bot walls
 │ real browser, natural-language goal,             │   $0.016/step, opt-in,
 │ output_schema → typed JSON, hard time limit      │   max 1 run per scan
 └──────────────────────────────────────────────────┘
                       │
                       ▼
   ④ Extract → ⑤ Match → ⑥ Score → report + removal steps
```

| TinyFish product | Our use | Why it matters |
|---|---|---|
| **Search** | Every query in [`plan.py`](../backend/app/pipeline/plan.py) runs through it. We use **`include_domains`** to aim queries at specific kinds of site (people-finders, social, professional, code, documents) and **`location`** to target the region the user lives in. | Domain-scoped queries are how one name becomes a map of *where* you're exposed. The snippets also feed our first "is this you?" filter, so we fetch only promising pages. |
| **Fetch** | The best candidates (up to `max_fetch_urls`, 20 by default) are batched **10 URLs per call** and returned as **markdown**. Batches run concurrently. | Clean markdown lets our rule-based extractor find phones, emails, addresses, employers, schools and family names near your name, with a quote from the page. **Structured per-URL errors** (`login_required`, `bot_blocked`) drive the next decision automatically. |
| **Agent** | Used only when a **people-finder** page returns `bot_blocked` / `login_required` from Fetch. We send a natural-language **goal** plus an **`output_schema`** and get typed JSON back (`phone`, `address`, `age`, `relatives`, `employer`, …). | People-finder sites are the **highest-risk** source (phone plus address plus relatives on one page) and also the hardest to read. The Agent covers that gap. |

## 2. How we use TinyFish well

**Escalate only when needed.** Each step is more powerful and more expensive than the last, and we move up only on a concrete signal:

1. A search snippet alone often answers the question. Candidates scored below the threshold never get fetched.
2. Login-walled social sites (LinkedIn, Instagram, X and others, listed in YAML) are **never fetched**. We use the public snippet only.
3. The Agent runs only for a **broker** page that Fetch reported as **blocked**, only if `agent_enabled: true`, and at most `max_agent_runs` times per scan.

As a result, a default scan costs **$0** on TinyFish's free allowance, and a scan with the Agent switched on costs a few cents. The `num_of_steps` from each Agent run is turned into a cost figure and reported as `cost_usd` on every report.

**Ethical guardrails in the Agent goal.** The prompt we send the Agent states the rules directly:

> *"Do not log in, sign up, pay, or submit any form. If a login, paywall or captcha appears, stop and return `{"blocked": true}`."*

Combined with `max_duration_seconds` and a strict `output_schema`, this keeps the Agent to **public pages only**, it can't run up costs, and its output can be checked against the schema.

**Resilience built around TinyFish** ([`tinyfish.py`](../backend/app/tinyfish.py)):

| Mechanism | Behaviour |
|---|---|
| Retries with backoff | Transport errors and 429 / 5xx responses are retried, and `Retry-After` is honoured |
| **One circuit breaker per product** | Three consecutive failures disable *that* product (Search, Fetch or Agent) for five minutes, while the others keep working |
| Graceful degradation | If Fetch fails, we fall back to the Search snippet. If a search fails, that source is marked "failed" and the scan continues. The report is flagged `partial` instead of crashing |
| Per-product timeouts | Search 10 s, Fetch 150 s, Agent 120 s (`config.yaml`) |
| Live observability | Each Search, Fetch and Agent call is streamed to the UI as a source event (*checking → ok / blocked / failed*), and `/health` shows the state of each breaker |

## 3. Why TinyFish, and not a plain search API plus a scraper

| Need | Plain search API + `requests` | TinyFish |
|---|---|---|
| Find mentions across specific *kinds* of site | Manual `site:` hacks | `include_domains` + `location` built in |
| Read modern JS-heavy pages | Mostly empty HTML | Fetch returns rendered markdown |
| Know *why* a page failed | A generic 403 | Typed errors (`bot_blocked`, `login_required`) that our logic acts on |
| Read people-finder sites that block bots | Not possible without building a headless-browser stack | **Agent**, with a goal and a schema |
| Structured output from a messy page | Custom parser per site | `output_schema` → typed JSON |
| Cost control | Self-hosted browsers, proxies, maintenance | Free Search/Fetch allowance, pay-per-step Agent |

TinyFish lets a small team build in one weekend what would otherwise need a search vendor, a headless-browser fleet and a parser per site: a scan that reaches the whole web, from simple pages up to bot-protected people-finders.
