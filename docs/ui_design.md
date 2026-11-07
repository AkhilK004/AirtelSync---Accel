# UI and UX design record

Audience: a shop owner or clinic doctor on a mid-range phone, often Hindi-first, one-handed, on slow data, deciding on a monthly bill and wary of paperwork. The job: trust, then price, then documents, without feeling like a form.

## Idea: the shop counter
Indian small business runs on painted signboards, the khata (ledger) and printed bill slips. The interface borrows that vocabulary. **The one bold move is the quote as a bill slip** (dotted ledger rows, serif rupee total, torn edge). Toggling an add-on stamps a line onto the slip and the total flashes once. Everything else stays quiet.

## Tokens (`web/app/globals.css`)
| Token | Value | Use |
|---|---|---|
| Neel (indigo ink) | `#1b2a6b` | headings, structure, selected states |
| Haldi (turmeric) | `#f2b705` | the one primary action per screen (ink text on it, about 7:1) |
| Chalk | `#f6f7fb` | page background (cool white, not cream) |
| Mehendi | `#2f6b4f` | included / approved |
| Mirchi | `#b8281f` | errors, holds |
| Text / muted | `#1a1d2e` / `#565b70` | body / secondary (5.9:1 on chalk) |
| Control border | `#7f87a6` | inputs, switch tracks (3:1 on white) |

Type: **Mukta** for UI and body (Devanagari and Latin designed together), **Tiro Devanagari Hindi** (print serif) for headlines and rupee totals. Hindi and Marathi are set at 17px with line-height 1.7. Sentence case, no all-caps labels.

## What changed, by screen
- **Header:** wordmark with a turmeric bar, segmented language switch, "larger text" button (scales the whole UI, remembered).
- **Landing:** starts with the real input ("Tell us about your business") and three example chips; what is typed becomes the advisor's first message. One primary button, plus a link to answer step by step.
- **Advisor:** short bubbles; progress as segments ("2 of 6 answered"); quick replies wrap instead of scrolling sideways; the long recommendation text sits behind "Show details" while a plan slip with the price and one button is shown; a typing indicator; the duplicate "see full price" chip is hidden when the slip is shown.
- **Quote:** the bill slip; extras below with a switch each; assumptions as a list; breakdown with dotted leaders; sticky total and continue bar.
- **KYC consent:** the notice reads as labelled lines (who we are, what we collect, why, how long, your rights) instead of one bullet wall; the "tick both required options" hint is a visible notice, not small grey text.
- **Back-office, checkout, tracker:** take the new tokens and fonts; layouts unchanged.

## Accessibility
axe-core (WCAG 2.0/2.1/2.2 A and AA plus best practices) run on landing, advisor, quote, checkout, KYC consent and the tracker gate, in English, Hindi and Marathi, at 375 px and 1280 px: **0 violations** after fixes (the audit first found a brand-link name mismatch and a missing main landmark and heading on the advisor). Also in place: skip link, per-locale `lang`, visible focus ring, 44 px minimum targets, polite live region for chat, reduced-motion respected, no horizontal scroll at 375 px.

Not covered by automation: real screen-reader use, keyboard-only walk-through of every state, and native-speaker review of Hindi and Marathi copy. Re-run: the `scripts/e2e_*.mjs` tests and `scripts/a11y_axe.mjs`.

## Tools
The AccessLint and Impeccable plugins were installed during this work but only load after a session restart, so they were **not used**; the design pass followed the frontend-design skill and the audit used axe-core directly. The Bencium plugin was not installed.
