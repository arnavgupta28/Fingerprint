# Fingerprint: sources

Where Fingerprint looks, what it can find there, and how a user can remove it. Everything here is **public**: no logins, no paywalls, no purchased data.

## 1. Source groups

| Group | Examples | What it can reveal | Method | Level needed |
|---|---|---|---|---|
| **Web search** | Brave Search, Exa | Anything indexed: bios, news, résumés, PDFs | Search API | Light |
| **Professional** | LinkedIn (public profile), GitHub, company "team" pages | Employer, role, work history, city | Search API (`site:`) → Fetch | Light |
| **Social** | X, Instagram, Facebook, Reddit, YouTube (public pages) | Photos, location hints, family/friends, username reuse | Username probe + search | Standard |
| **Breaches** | Have I Been Pwned | Which breaches your email is in, and what leaked (passwords, phone, etc.) | HIBP API | Standard |
| **People-finders / data brokers** | Truecaller-style lookups, public directories, broker listings | Phone, address, age, relatives | Search → Fetch → Agent if needed | Deep |
| **Documents** | Public PDFs, conference lists, alumni pages | Email, phone, school, year of study | Search (`filetype:pdf`) → Fetch | Deep |
| **News & records** | News sites, public notices, court/registry listings where public | Events, addresses, legal mentions | Search → Fetch | Light |
| **Code & dev** | GitHub commits, npm/PyPI author fields, Pastebin-style sites | Personal email, leaked keys, real name ↔ username link | Search + API | Standard |

## 2. Source config (YAML)

New sources are added in `config/sources.yaml`. No code changes needed.

```yaml
- id: github
  name: GitHub
  group: code
  method: api            # search | fetch | agent | api
  min_level: standard
  needs: [username]
  url_template: "https://api.github.com/users/{username}"
  rate_limit_per_min: 30
  removal_playbook: github_privacy
  verified: true
```

User-added or unverified sources are **never** allowed to create a 🔴 high-risk finding until reviewed.

## 3. Removal playbooks

Each finding links to a playbook in `config/playbooks.yaml`:

| Playbook | Steps (summary) |
|---|---|
| `peoplefinder_optout` | Open the opt-out page → find your listing → submit removal → recheck in 7 days |
| `breach_response` | Change password on that site + anywhere reused → turn on 2FA → use a password manager |
| `social_lockdown` | Make profile private → remove phone/location from bio → hide friends list |
| `google_results_removal` | Use Google's "Results about you" tool to request removal of contact details |
| `github_privacy` | Enable "Keep my email private" → use the noreply email for commits |
| `old_document` | Contact site owner for takedown; ask search engines to drop the cached copy |
| `linkedin_visibility` | Edit public profile visibility → hide contact info and connections |

## 4. Fetching etiquette

- Max 1 request/second per domain; honour `robots.txt`.
- Honest User-Agent: `FingerprintBot/0.1 (+contact)`.
- Cache pages by URL hash (short TTL). Cache **pages**, never **people**.
- If a page needs a login or CAPTCHA, stop and mark it "couldn't check".
