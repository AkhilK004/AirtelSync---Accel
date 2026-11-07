# Udyam Digital — Accel Business (Airtel SYNC / YTL Hackathon 2026, Enterprise Track A)

A small business finds the right bundle, sees **one transparent monthly price**, passes a **smart KYC** check and gets a **tracker** — in Hindi, English or Marathi. **All data in this repo is synthetic.** The app is branded as a fictional "Accel Business"; no Airtel branding is used.

| Challenge deliverable | Where |
|---|---|
| D1 Advisor (GenAI, recommends from the catalogue, explains) | `api/app/advisor`, `/[locale]/advisor` |
| D2 Quote & checkout (single price, toggleable add-ons) | `api/app/engine`, `/[locale]/quote`, `/[locale]/checkout` |
| D3 Smart KYC (extraction, validation, mocked GSTIN / Udyam, consent) | `api/app/kyc`, `api/app/consent`, `/[locale]/kyc` |
| D4 Tracker | `api/app/orders`, `/[locale]/track` |
| D5 Video script + repo | `docs/video_script.md` |
| D6 Architecture diagram | `docs/architecture.md`, `docs/charts/architecture.png` |
| D7 Business case (≤ 10 slides) | `docs/slides_outline.md` |
| D8 1-page privacy & security note | `docs/privacy_note.md` |
| S1 / S2 Back-office + propensity score | `/backoffice`, `api/app/leads` |

Design rule: **the LLM never decides price, eligibility, or a KYC outcome.** It extracts facts and phrases replies; deterministic, tested code owns the business decisions (`docs/architecture.md`).

## Run it locally (about 5 minutes, no cloud account needed)
Prerequisites: Python 3.12+ with `pip`, Node 22+, (optional) Docker.

```bash
# 1. API  (uv is the package manager)
pip install uv
cd api
python -m uv sync                      # installs deps, creates .venv
cp .env.example .env                   # defaults are fine for local
LLM_PROVIDER=fake SEED_ON_START=true python -m uv run uvicorn app.main:app --reload --port 8000
#   LLM_PROVIDER=fake  = offline rule-based understanding + template replies (no credentials)
#   SEED_ON_START=true = demo leads for the back-office + 3 live demo orders

# 2. Web (second terminal)
cd web
cp .env.local.example .env.local       # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev                            # http://localhost:3000  (redirects to /en)
```
The model file `data/derived/propensity.joblib` is git-ignored: create it once with `cd api && python -m uv run python ../scripts/train_propensity.py`.

Open http://localhost:3000/hi (Hindi), `/en`, `/mr`. The checkout **OTP is `123456`**. Try the one-shot message *"meri pharmacy hai Lucknow mein, 3 log kaam karte hain, GST hai"*.

### Demo logins and tokens (local defaults — change for any real deployment)
| What | Value |
|---|---|
| Back-office `/backoffice` | `admin` / `change-me` |
| Admin endpoints (`X-Admin-Token`) | `change-me` |
| Tracker demo button | open `/en/track/<order>?demo=1` (needs `NEXT_PUBLIC_DEMO_ADMIN_TOKEN=change-me` at web build) |
| Seeded demo orders | phone last 4 digits `0001`, `0002`, `0003` (ids returned by `POST /admin/reset`; the seeded stuck-KYC order also appears as a back-office lead) |

Specimen KYC documents for 12 applicants are in `data/raw/kyc_documents`; upload e.g. `K03_*.png` (approved) or `K11_*.png` (stale bill). Offline, extraction reads a transcription fixture, so only those specimen images are "readable" (see `docs/assumptions.md` A34).

## Tests and evaluations
```bash
cd api
python -m uv run pytest -q                                        # 165 tests, offline (fake LLM)
python -m uv run python ../scripts/run_scenarios.py               # 17 advisor scenarios (add --base-url / --provider gemini)
python -m uv run python ../scripts/eval_kyc.py                    # 12 KYC applicants vs docs/kyc_expected.csv (DRAFT answer key)
cd ../web && npm run lint && npm run build
```
Browser smoke tests (Playwright, not part of the web deps) are in `scripts/e2e_*.mjs`; setup notes are at the top of each file.

## Configuration (`api/.env.example`)
`APP_ENV`, `STORAGE` (`memory` | `firestore`), `LLM_PROVIDER` (`gemini` | `fake`), `GEMINI_MODEL`, `GCP_PROJECT`, `GCP_LOCATION`, `GOOGLE_API_KEY`, `GCS_REVIEW_BUCKET`, `BACKOFFICE_USER` / `BACKOFFICE_PASSWORD`, `ADMIN_TOKEN`, `CORS_ORIGINS`, `GST_RATE`, `DATA_DIR`. Extras: `SEED_ON_START`, `RATE_LIMIT_ENABLED`. With `APP_ENV=prod` the API refuses to start on default secrets.

## Live Gemini
Set `LLM_PROVIDER=gemini` with Vertex AI credentials (`gcloud auth application-default login`, `GCP_PROJECT`) or an AI Studio `GOOGLE_API_KEY`. **The live model has not been run against the scenarios or KYC specimens yet**: all green results above are the offline path. Expect to tune prompts on the first live run.

## Deploy
`docs/deploy.md` and `scripts/deploy_gcp.sh` (dry-run by default). **Not deployed yet.** A local Docker dry run passed (`docker build -t udyam-api .`).

## Repository map
```
api/            FastAPI app (app/), tests, config/*.yaml (bundle templates, fulfilment, routing)
web/            Next.js app (locales en / hi / mr) + English-only /backoffice
data/raw/       synthetic dataset (read-only)   data/derived/  city tiers, i18n names, KYC fixture, model (generated)
scripts/        train / eval / scenarios / seed / deploy / e2e / slide numbers
docs/           data_contract, assumptions (A1–A56), findings, architecture, privacy note, slides, video script, deploy
PLAN.md         implementation plan the build followed
```

## Honest status
Done and tested offline: everything in the table above. **Not done:** live Gemini validation, cloud deployment, native-speaker review of Hindi / Marathi strings, human verification of `docs/kyc_expected.csv`, slides and video (outline + script only), PAN + bill KYC path (shown as "coming soon"), voice (stretch). Every judgement call is listed in `docs/assumptions.md`.
