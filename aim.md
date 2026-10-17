# Fingerprint: our aim

> **See what the internet knows about you, before someone else does.**

<p align="center"><img src="assets/mascot/smudge.svg" width="160" alt="Smudge, the Fingerprint mascot"></p>

---

## 1. The problem

Over the years, bits of our lives end up online: an old social profile, a résumé, a news mention, a leaked email in a data breach, or a "people-finder" site listing our phone number and home area.

Each piece looks harmless by itself. **Put together, they become a fingerprint**: enough for a scammer to impersonate you, guess your passwords, or find where you live.

Most people **don't know what's out there**. Checking means hours of searching, and you still won't know whether you've found everything or what to do about it.

## 2. What Fingerprint does

You tell Fingerprint a little about yourself, and it searches the public internet and gives you a clear report:

1. **What it found**: your details, grouped by type (contact, location, work, photos, accounts, breaches).
2. **Where it found them**: a link to every source.
3. **How risky it is**: a simple exposure score plus a 🟢 / 🟡 / 🔴 label on each item.
4. **What you can do**: a step-by-step way to remove or lock down each item.

## 3. You choose how much to share

Three things are **required**, because without them we can't tell you apart from people with the same name: **your name, your phone number and your city**. Everything else is **your choice**, and each extra detail makes the match sharper.

| Level | You enter | What you get |
|---|---|---|
| **Light** | Name, phone, city | Where your number and name show up, including people-finder sites |
| **Standard** | + birth year, email, usernames | Data breaches, accounts using your handle, and age matching against listings |
| **Deep** | + other names, workplace, school, past cities | The most precise picture, with the fewest mix-ups |

Every source in the report shows a **confidence score**: *Very likely you*, *Likely you*, *Maybe you* or *Probably not you*. You can answer **"Is this you?"** to correct it. ([Why we ask for these fields](docs/INPUT-FIELDS.md))

## 4. Who it's for

- **Everyday people** who want peace of mind, or who just got a suspicious call that knew too much.
- **People at higher risk**, like journalists, creators, survivors of harassment, and anyone with a public role.
- **Job seekers**, to see what a recruiter sees when they Google you.

## 5. Our promises (privacy by design)

A tool that finds personal data must not become a tool for stalking. So:

- **For searching yourself only.** Users confirm they are searching for themselves before every scan.
- **Nothing is stored.** Your inputs and report are deleted when you close the session, unless you choose to download them.
- **Sensitive data is partly hidden.** Phone numbers and addresses are shown masked (e.g. `98•••••210`), so the report itself isn't a leak.
- **Public pages only.** We never log in, bypass paywalls, or buy data.
- **Every finding has a source.** We show proof, not guesses.

## 6. What success looks like

A user enters their name, phone and city and, **in under 2 minutes**, sees:

> *"We found **14** public items about you. **3 are high-risk**: your mobile number on a people-finder site, your email in 2 data breaches, and your home area in an old résumé. Here's how to fix each one."*

Then they **act on it**: they remove a listing, change a password, or lock down a profile.

## 7. Scope for the hackathon

| ✅ Must have (demo) | 🟡 Nice to have | ❌ Not doing |
|---|---|---|
| Choose your detail level (Light / Standard / Deep) | Downloadable PDF report | Searching for *other* people |
| Live internet search with sources | Re-scan monthly and alert on new items | Dark-web monitoring |
| "Is this you?" confirm / reject | Auto-filled removal request emails | Logging in to sites or scraping private data |
| Exposure score + risk labels | Photo / face matching | Storing user data on our servers |
| Removal steps for each finding | Multi-language | Selling or sharing any data |
| Smudge, the mascot, guiding the user | | |

## 8. One-line pitch

> **Fingerprint shows you your digital footprint (what's public about you, where, and how risky it is) and helps you clean it up. You choose how much to share; we keep none of it.**

---

*Event details: [HACKATHON.md](HACKATHON.md) · Build plan: [PLAN.md](PLAN.md) · How it works: [ARCHITECTURE.md](ARCHITECTURE.md)*
