# Demo video script (≤ 3:00)

Setup: API with `SEED_ON_START=true`, web built with the demo token, phone-size browser (375 px). Screenshots/recording at 1080×1920 or a phone mirror. Use the seeded demo orders (phone last digits 0001–0003) for the tracker and back-office.

| Time | Screen | What to show / say |
|---|---|---|
| 0:00–0:20 | Slide: funnel chart | "5,000 leads became 368 customers. 17.6 days, three status calls, ₹15,000 to win each one. The biggest drop is quote to yes: 44%." |
| 0:20–1:10 | `/hi/advisor` | Type one Hinglish message: *"meri pharmacy hai Lucknow mein, 3 log kaam karte hain, GST hai"*. Advisor asks only the one missing question (locations), then recommends **Dukaan Starter** in Hindi, with one-line reasons. Tap "यह प्लान क्यों?" to show the explanation uses the owner's own answers. Say: "The AI understands and explains; prices come from rules." |
| 1:10–1:35 | `/hi/quote/…` | One big total. Toggle **CCTV** on: total updates from the server and the toast says what it pulled in. Open price breakdown (GST, setup). Mention assumptions chips. |
| 1:35–2:15 | `/hi/kyc/…` | Consent screen (3 languages, marketing off). Enter a GSTIN → prefill from registry. Upload the **K11** documents: result says the bill is older than 90 days with the fix "upload a bill dated after 16 Apr 2026". Then show **K06**: GSTIN typo caught by the check digit. |
| 2:15–2:35 | `/hi/track/…?demo=1` | Digital products already "चालू"; physical ones show install ETA; press Advance to show technician assigned and the WhatsApp-style messages. |
| 2:35–2:50 | `/backoffice` | Leads ranked by expected monthly value, each with its three score reasons. Point at a **KYC assist: Udyam path** badge (a GSTIN-less lead stuck at KYC: the system says what to do, not just a score) and the red **GSTIN suspended** row in the Compliance hold queue (never pushed to sales). Funnel panel with baseline vs target. Say: "Calling the top 30% of leads reaches 58% of activations." |
| 2:50–3:00 | Slide: targets | "Seven to fourteen percent activation, seventeen days to five, three status calls to under half a call." |

## Recording checklist
- Run `python -m uv run pytest -q`, `scripts/run_scenarios.py`, `scripts/eval_kyc.py` the day before and say the numbers only if they are green **on the live Gemini run**.
- Do not claim the live deploy or the live Gemini results unless they were actually run (see `docs/deploy.md`).
- Hindi strings were written by the team without native-speaker review: have someone read them before recording.
- Keep the specimen-document banner visible: all data is synthetic.
