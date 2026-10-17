# What we ask for, and why

Fingerprint asks only for what measurably improves the match. This page records the research behind the form and how each field feeds the confidence score shown on every source.

## 1. What similar services ask for

| Service | Required | Optional | How they match |
|---|---|---|---|
| **Optery** (data-broker removal) | First name, last name, **year of birth**, current city, current state | Middle name, birthdate, current & past addresses, unlimited name aliases (maiden, nicknames) | Compares results with your name, city, state, age, phone and email |
| **DeleteMe** | Full name, date of birth, current + past addresses, phone, email | Gender, employer, LinkedIn URL, relatives | Builds a "datasheet" and searches brokers with it |
| **Incogni** | First, middle, last name, date of birth, full home address (US: **phone required**) | Extra emails / addresses (up to 3) | Broker opt-out requests using those details |
| **Google "Results about you"** | Name + **phone, email, home address** | Nicknames, maiden names, more phones / addresses / emails | Alerts when Search shows your contact details |
| **People-search sites** (Spokeo, Whitepages, …) | Name + location | Age range, middle initial, relatives, past addresses | Separate namesakes by age, middle initial, places, relatives |
| **OSINT self-audit** (Sherlock, WhatsMyName, Maigret) | A username / email / phone | Old handles | Exact identifier lookups across hundreds of sites |

**Entity-resolution practice:** names alone aren't unique. Phone and email are the strongest identifiers. Birth year matches with ±1–2 years of tolerance. City/state corroborate but don't identify.

## 2. Our fields

| Field | Required? | Why | Used for |
|---|---|---|---|
| **Full name** | ✅ Required | Every listing is keyed on a name | Name queries; "full name" signal |
| **Phone number** (+ country code) | ✅ Required | The most identifying thing about you, and what scammers use. Google, Incogni and DeleteMe all ask for it | 4 phone formats searched; phone on people-finders; "phone" signal (strongest) |
| **City** | ✅ Required | The minimum location every broker shows; the first namesake filter (Optery requires it) | `"Name" City` queries; "city" signal |
| **Country** | ✅ Required (defaults to India) | Sets search region and phone country code | TinyFish `location`; phone normalisation |
| Birth year | Optional (Standard+) | Brokers show ages; the #1 namesake tie-breaker (Optery requires it) | "age fits" signal **or** "age doesn't match" penalty |
| Email | Optional (Standard+) | Unique identifier; also unlocks breach + Gravatar checks | Email query; breaches; "email" signal |
| Usernames (≤ 3) | Optional (Standard+) | Handles link accounts across sites (Sherlock-style) | 3 queries each + 6 platform checks; "username" signal |
| State / region | Optional (Standard+) | Separates same-name cities and corroborates listings | "state" signal |
| Middle name | Optional (Deep) | Brokers show middle initials; a different initial suggests a namesake | "middle name" signal or "different middle initial" penalty |
| Other names (≤ 3) | Optional (Deep) | Maiden names / nicknames (Optery, Google) | Extra name queries; matched like your full name |
| Workplace | Optional (Deep) | Professional pages and résumés | Query + "employer" signal |
| School / college | Optional (Deep) | Alumni lists, old PDFs | Query + "school" signal |
| Past cities (≤ 3) | Optional (Deep) | Brokers keep address history | Queries + "past city" signal |

**Not collected (on purpose):** full date of birth, street address, government ID, relatives' names. They'd sharpen matching slightly, but asking for them would make Fingerprint itself a sensitive dataset.

## 3. How confidence is calculated (`backend/app/pipeline/match.py`)

Every source card shows a **confidence on the right**: how sure we are that page is about *you*.

| Signal | Weight |
|---|---|
| Your phone number on the page | +0.55 |
| Your email on the page | +0.50 |
| Your username (in the URL or as @handle) | +0.30 |
| Your full name / another name you gave | +0.25 |
| First + last name close together | +0.12 |
| An age / birth year that fits yours (±1–2 years) | +0.20 |
| City · workplace · school · past city · state · middle name | +0.15 · 0.15 · 0.10 · 0.08 · 0.05 · 0.05 |
| **Age that contradicts your birth year** | −0.35 |
| **Different middle initial** | −0.10 |
| **Page lists many people's numbers** (phone directory) | −0.15 |

**Caps:** name only ≤ 35% · name + one detail ≤ 60% · no name on the page ≤ 70%. Your own phone/email on a page with your name sets it to at least 90%.

| Confidence | Label | Colour |
|---|---|---|
| ≥ 75% | Very likely you | green |
| 50–74% | Likely you | blue |
| 30–49% | Maybe you | amber |
| < 30% | Probably not you | grey |

"Yes, me" / "Not me" on a card overrides the score for the whole source and re-scores the report.

## Sources

- Optery: [Manage profile](https://help.optery.com/en/category/manage-profile-119g9fr/) · [Getting started](https://www.optery.com/getting-started/) · [Phone & email scan preferences](https://help.optery.com/en/article/configuring-your-phone-and-email-scan-preferences-1jw9ipy)
- DeleteMe: [What information do you need to sign up](https://help.joindeleteme.com/hc/en-us/articles/17492365457811-What-information-do-you-need-to-sign-up)
- Incogni: [Getting started](https://support.incogni.com/hc/en-us/articles/4905856866450-Getting-started-with-Incogni) · [PCWorld review](https://www.pcworld.com/article/2958237/incogni-review.html)
- Google: [Find and remove personal contact info](https://support.google.com/websearch/answer/12719076?hl=en)
- Matching practice: [Cognyte: entity resolution](https://www.cognyte.com/blog/entity-resolution-etl/) · [Accurint person search help](https://www.accurint.com/help/bps/irs/pdf/advanced_person_help.pdf) · [Enformion: people search](https://www.enformion.com/blog/people-search-finding-anybody)
- OSINT self-audit: [Peter Bassill: OSINT self-audit](https://www.peterbassill.com/privacy/osint-self-audit) · [IT-Connect: three OSINT tools](https://www.it-connect.tech/what-accounts-do-you-really-have-online-three-osint-tools-to-find-out/)
