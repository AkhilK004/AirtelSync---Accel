# Deploy runbook (Phase 8)

Status: **image build, hardening and a local dry run are done; nothing is deployed to GCP.** The only authenticated gcloud project (`geoseolab`) is unrelated to this hackathon, so the cloud deploy was deliberately skipped pending a project you choose.

Dry run done (local Docker, `LLM_PROVIDER=fake`, memory store, seeded): image `udyam-api` builds (1.95 GB, trains the model at build time, runs as non-root user), `/health` ok, **17/17 advisor scenarios pass over HTTP against the container**, a full consent -> upload -> KYC -> order flow works (K03 approved -> `INSTALL_SCHEDULED`), back-office and admin reject missing/wrong credentials, security headers present, and the container log contains no full phone number.

## What gets deployed
| Piece | Where | Notes |
|---|---|---|
| API | Cloud Run `asia-south1`, `--min-instances 1 --max-instances 1` | single instance on purpose: KYC uploads wait in process memory until evaluation (A38) and the rate limiter is per instance |
| Data store | Firestore Native `asia-south1` (`STORAGE=firestore`) | collections: sessions, quotes, orders, consents (append-only), kyc_applications, leads, events, audit_log, meta |
| Review images | GCS bucket `asia-south1`, 1-day lifecycle delete | only manual-review documents are ever written |
| LLM | Gemini on Vertex AI `asia-south1` (`gemini-3.5-flash`) via the service account (no API key) | fallback: `GOOGLE_API_KEY` with `GCP_PROJECT` empty |
| Web | Cloud Run (image from `web/Dockerfile`) **or** Vercel | `NEXT_PUBLIC_API_URL` is baked at build time |

## One command (dry-run by default)
```bash
PROJECT=<project-id> ./scripts/deploy_gcp.sh            # prints every command, changes nothing
PROJECT=<project-id> RUN=1 ./scripts/deploy_gcp.sh      # executes
```
It enables APIs, creates Firestore + the bucket + lifecycle rule, a least-privilege service account (`datastore.user`, `aiplatform.user`, bucket `objectAdmin`), deploys the API from the root `Dockerfile` (trains the propensity model at build time), generates strong `ADMIN_TOKEN` / `BACKOFFICE_PASSWORD` and prints them once. The API **refuses to start in `APP_ENV=prod` with the default `change-me` secrets**.

After the web URL exists, rerun with `WEB_ORIGIN=<web url>` so CORS allows it (the API only allows listed origins).

## Human steps (cannot be automated)
1. Pick / create the GCP project and enable billing; **set a budget alert** (min-instance Cloud Run + Firestore + Vertex AI cost money).
2. Run the deploy, store the printed admin token and back-office password.
3. Verify on the live URL (below), then on a real phone in Hindi.

## Verify against the deployed API
```bash
cd api
python -m uv run python ../scripts/run_scenarios.py --base-url https://<api-url> --provider gemini   # 17 advisor scenarios
LLM_PROVIDER=gemini python -m uv run python ../scripts/eval_kyc.py --provider gemini                    # needs Vertex credentials locally (gcloud auth application-default login)
curl https://<api-url>/health                                                                            # shows counts + BUILD_SHA
```
`run_scenarios.py --base-url` talks to the live HTTP API, so the LLM mode is whatever the service runs (Gemini). The first live Gemini run has **not** happened yet: expect to tune NLU prompts / the rule fallbacks if a scenario fails.

## Hardening in place
- Upload checks: 5 MB cap, content sniffing (PNG/JPEG/PDF only, client MIME ignored), bounded read.
- LLM calls: 15 s timeout, one retry, then template reply (advisor) / "please re-upload" (KYC). NLG output that invents a price/percent/product is replaced by the template.
- Rate limits per client IP (in memory): session/chat 30/min, KYC 60/min, OTP 10/min, checkout 20/min, consents 30/min; per session 80 messages.
- Security headers (`nosniff`, `X-Frame-Options: DENY`, `no-store`), CORS allow-list, redaction filter on logs (phones, GSTIN, PAN, 12-digit ids, emails).
- Back-office: Basic auth, constant-time compare; admin endpoints need `X-Admin-Token`.
- `/health` returns record counts and `BUILD_SHA`.

## Known limits
- `FirestoreRepo` is tested against an in-memory fake client, **not** a real Firestore.
- `SEED_ON_START=true` seeds demo leads/orders once (skipped when `meta/demo` exists); `/admin/reset` wipes all collections. Turn both off for anything real.
- `NEXT_PUBLIC_DEMO_ADMIN_TOKEN` (tracker "advance" and back-office reset buttons) is visible in the browser bundle: use a demo-only token and rotate after the demo.
