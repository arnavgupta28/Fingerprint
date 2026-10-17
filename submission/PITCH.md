# Fingerprint: the pitch

## The 30-second version

> Scam calls that know your name, your employer and your city aren't luck. That information is on the public internet, scattered across old profiles, résumés, people-finder sites and data breaches. Each piece looks harmless alone. **Together they form a fingerprint** that scammers, stalkers and identity thieves can use.
>
> **Fingerprint** lets you see that fingerprint first. You tell it as much or as little about yourself as you like. Its agents search the live web with TinyFish, read every page that mentions you, and show you what's exposed, exactly where, how risky it is, and how to remove it. You keep control of what you share, and we keep none of it.

## The 10-second version

> **Fingerprint shows you what the internet knows about you, where it lives, how dangerous it is, and how to delete it, without ever storing your data.**

---

## 1. The real-world problem

- **Personal data is scattered, and the pieces add up.** A LinkedIn headline gives your employer. An old conference PDF has your phone number. A people-finder site lists your area. A breach leaked your email and password. Combined, that is enough to impersonate you, reset your passwords, or find your home.
- **Most people can't see it.** Checking by hand means hours of searching, and even then you don't know whether you found everything, whether a result is really you or someone with the same name, or what to do about it.
- **The tools that exist don't fit everyday users.** Breach checkers cover one email. Paid data-removal services ask you to hand over all your personal details first, cover mainly US data brokers, and charge a subscription. OSINT tools are built for investigators, not for the person being investigated.
- **The harm is real and growing.** Targeted phishing, SIM-swap fraud, impersonation scams, doxxing of journalists and creators, and stalking all start with the same step: collecting public crumbs about the target.

## 2. What Fingerprint does

1. **You choose how much to share.** *Light* uses your name and city. *Standard* adds an email or username. *Deep* adds a phone number, employer, school and past cities. The API drops any field your chosen level doesn't allow, so a Light scan never touches your email.
2. **It searches the live web.** Up to 24 targeted TinyFish searches cover professional sites, social media, code sites, documents, people-finders and news, alongside free checks for data breaches, Gravatar, and your username on six platforms.
3. **It reads the pages.** TinyFish Fetch turns the pages that mention you into clean text. When a people-finder blocks a plain fetch, a TinyFish Agent can open it in a real browser and return only what it publicly shows. The Agent is opt-in, capped, and never logs in, signs up, pays or submits a form.
4. **It proves every finding.** Each finding carries its source URL, a short quote from the page, a confidence score, and the reasons we think it's you ("full name + city + employer").
5. **It handles namesakes.** Each finding has an **"Is this you?"** button. Clicking *Not me* removes everything from that page and recalculates your score immediately.
6. **It tells you what to do.** You get a 0–100 exposure score, a 🟢 / 🟡 / 🔴 label on each item, and a removal playbook for each one: opt out of a people-finder, respond to a breach, lock down a social profile, hide your email on GitHub, or ask Google to drop your contact details.

## 3. Who it's for

| User | Why they need it |
|---|---|
| **Everyday people** | Just had a scam call that knew too much, or want peace of mind |
| **People at higher risk** | Journalists, creators, activists, harassment survivors, and anyone with a public role, for whom exposure has physical consequences |
| **Job seekers** | Want to see what a recruiter sees before the interview |
| **Security teams (later)** | Employee exposure audits, since social engineering targets staff through their public footprint |

## 4. What's new about it

| Existing approach | What Fingerprint does differently |
|---|---|
| Breach checkers look up **one identifier** in **one database** | We correlate name, city, email, username, phone, employer and school across the **whole live web**, plus breaches |
| Removal services ask for **everything up front** and keep it | **Progressive disclosure.** You choose Light, Standard or Deep, and we store **nothing**. Sessions live in memory and expire in 30 minutes |
| Search results are a **wall of links** with no guidance | Every item is **structured** (type, risk, evidence, confidence, reasons) and comes with a **removal playbook** |
| Namesakes produce **false alarms** | **Explainable match confidence** plus a one-click "Is this you?" loop that recalculates the score live |
| Scanners **show the raw data** back to you | The report is **masked** (`98•••••210`), so a screenshot or shoulder-surfer can't turn it into a doxx |
| LLM-based tools **send your personal data to a model** | Planning and extraction are **deterministic and rule-based**: no personal data goes to an LLM, results are repeatable, and nothing is hallucinated. No quote, no finding |
| Most scrapers **break on JS-heavy or bot-protected pages** | TinyFish's **Search → Fetch → Agent** escalation reads plain pages cheaply and uses a real browser agent only when it's needed |
| Tools can be **turned against other people** | Self-search consent is enforced by the API, scans are rate-limited per IP, there is no bulk mode, and output is masked |

**In short:** Fingerprint turns OSINT, the technique attackers use, into a privacy tool for the person being targeted, built so that it can't easily become the attack tool itself.

## 5. What success looks like

A user enters their name and city and, in under two minutes, sees:

> *"We found **14** public items that may be about you. **3 are high-risk** (phone number, people-finder listing, data breach). Exposure: high (68/100)."*

They tap *Not me* on a namesake, the score drops, and they open the removal steps for the people-finder listing. **Success is the user deleting a listing, changing a reused password, or locking down a profile.**

## 6. Where it goes next

- **Monthly re-scan and alerts** (opt-in storage), since data brokers often re-list removed entries
- **Auto-drafted opt-out and DPDP / GDPR erasure requests** for each finding
- **Verified ownership** (an OTP to your email or phone) before Standard or Deep scans
- **B2B:** employee exposure audits for security teams, and a lighter version for HR onboarding
- **Business model:** free scan, paid monitoring plus assisted removal, and B2B audits
