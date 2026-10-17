# Fingerprint: design

## Feel
**Calm, friendly, trustworthy.** The topic (your exposed data) can feel scary, so the UI should reassure rather than alarm: soft colours, plain words, and one clear next step on every screen.

## Meet Smudge 🫆

<p align="center"><img src="../assets/mascot/smudge.svg" width="200" alt="Smudge"></p>

**Smudge** is a small, round fingerprint with big eyes and a magnifying glass. Smudge is curious, kind, and a bit of a detective, the friend who helps you tidy up your online life.

| Moment | Smudge does | Line |
|---|---|---|
| Home | Waves | "Hi! Want to see what the internet knows about you?" |
| Level picker | Tilts head | "Share as little or as much as you like. More detail means a sharper search." |
| Consent | Holds up a hand | "Just checking: this is *you*, right?" |
| Scanning | Sniffs with the magnifier, bounces between source icons | "Looking through public profiles…" |
| Finding (red) | Gasps, covers mouth | "Found something worth fixing." |
| "Not me" clicked | Thumbs up | "Got it, ignoring that one." |
| Report | Points at score | "Here's your fingerprint. Let's clean it up together." |
| Item removed | Sparkles | "Nice, one less crumb!" |

## Colour tokens

| Token | Light | Dark | Use |
|---|---|---|---|
| `--brand` | `#6C5CE7` | `#8B7FF0` | Smudge body, primary buttons |
| `--brand-soft` | `#A29BFE` | `#5B4FCF` | Ridges, highlights |
| `--bg` | `#FAFAFF` | `#13121C` | Page |
| `--surface` | `#FFFFFF` | `#1D1B2A` | Cards |
| `--text` | `#1E1B2E` | `#ECEAF7` | Body text |
| `--risk-green` | `#16A34A` | `#4ADE80` | Low risk |
| `--risk-amber` | `#D97706` | `#FBBF24` | Medium risk |
| `--risk-red` | `#DC2626` | `#F87171` | High risk |

Risk is never shown by colour alone: always pair it with a label (Low / Medium / High) and an icon.

## Typography
- Headings: **Inter Tight**, 600
- Body: **Inter**, 400
- Masked values: monospace (**JetBrains Mono**) so the dots line up

## Key screens
1. **Home:** Smudge, the tagline "See what the internet knows about you", and a *Start scan* button.
2. **Level picker:** three cards (Light / Standard / Deep), each listing the fields it asks for and what you gain.
3. **Details + consent:** only the fields for the chosen level; consent checkbox; "We store nothing" note.
4. **Live scan:** source icons light up as Smudge checks them; findings slide in.
5. **Report:** exposure gauge (0–100), filter by category or risk, finding cards with *Is this you?*, source link, evidence, and *How to remove*.

## Animations
- Smudge idle: gentle 2 s bob (`translateY ±3px`).
- Scanning: the magnifier sweeps and the ridges shimmer (stroke-dashoffset loop).
- Respect `prefers-reduced-motion`: swap animations for static poses.

## Assets
- [`assets/mascot/smudge.svg`](../assets/mascot/smudge.svg): full mascot
- [`assets/logo/icon.svg`](../assets/logo/icon.svg): app icon / favicon (fingerprint + magnifier)
