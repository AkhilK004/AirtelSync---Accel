#!/usr/bin/env bash
# Deploys the API (and optionally the web app) to Cloud Run in asia-south1 with Firestore + a 1-day-TTL review bucket.
# SAFE BY DEFAULT: prints every command and changes nothing. Set RUN=1 to execute.
#
#   PROJECT=my-hackathon-project RUN=1 ./scripts/deploy_gcp.sh
#
# Needs: gcloud authenticated, billing enabled on PROJECT. Costs real money (Cloud Run min-instance, Firestore, Vertex AI).
set -euo pipefail
: "${PROJECT:?set PROJECT=<gcp project id>}"
REGION="${REGION:-asia-south1}"
API_SVC="${API_SVC:-udyam-api}"
WEB_SVC="${WEB_SVC:-udyam-web}"
BUCKET="${BUCKET:-${PROJECT}-udyam-review}"
SA="udyam-api@${PROJECT}.iam.gserviceaccount.com"
SHA="$(git rev-parse --short HEAD 2>/dev/null || echo dev)"
ADMIN_TOKEN="${ADMIN_TOKEN:-$(python -c 'import secrets;print(secrets.token_urlsafe(24))')}"
BO_PASSWORD="${BACKOFFICE_PASSWORD:-$(python -c 'import secrets;print(secrets.token_urlsafe(16))')}"
WEB_ORIGIN="${WEB_ORIGIN:-}"   # e.g. https://udyam-web-xxxx.a.run.app (or the Vercel URL); empty on first pass, rerun to set CORS

run() { echo "+ $*"; if [ "${RUN:-0}" = "1" ]; then "$@"; fi; }

run gcloud config set project "$PROJECT"
run gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com firestore.googleapis.com aiplatform.googleapis.com storage.googleapis.com

# Firestore Native in Mumbai (fails harmlessly if it already exists)
run gcloud firestore databases create --location="$REGION" --type=firestore-native || true

# Review-image bucket: 1-day lifecycle delete (the real retention enforcement)
cat > /tmp/lifecycle.json <<'JSON'
{"rule": [{"action": {"type": "Delete"}, "condition": {"age": 1}}]}
JSON
run gcloud storage buckets create "gs://${BUCKET}" --location="$REGION" --uniform-bucket-level-access || true
run gcloud storage buckets update "gs://${BUCKET}" --lifecycle-file=/tmp/lifecycle.json

# Least-privilege service account
run gcloud iam service-accounts create udyam-api --display-name="Udyam API" || true
run gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:${SA}" --role=roles/datastore.user
run gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:${SA}" --role=roles/aiplatform.user
run gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" --member="serviceAccount:${SA}" --role=roles/storage.objectAdmin

# API. max-instances 1: KYC uploads are held in process memory until evaluation (docs/assumptions.md A38) and the rate limiter is per instance.
run gcloud run deploy "$API_SVC" --source . --region "$REGION" --allow-unauthenticated --service-account "$SA" \
  --min-instances 1 --max-instances 1 --memory 1Gi --cpu 1 --timeout 60 \
  --set-env-vars "APP_ENV=prod,STORAGE=firestore,LLM_PROVIDER=gemini,GEMINI_MODEL=gemini-3.5-flash,GCP_PROJECT=${PROJECT},GCP_LOCATION=${REGION},GCS_REVIEW_BUCKET=${BUCKET},CORS_ORIGINS=${WEB_ORIGIN:-http://localhost:3000},BUILD_SHA=${SHA},SEED_ON_START=true,ADMIN_TOKEN=${ADMIN_TOKEN},BACKOFFICE_PASSWORD=${BO_PASSWORD}"

if [ "${RUN:-0}" = "1" ]; then
  API_URL="$(gcloud run services describe "$API_SVC" --region "$REGION" --format='value(status.url)')"
  echo "API: $API_URL   admin token: $ADMIN_TOKEN   back-office password: $BO_PASSWORD   (store these safely)"
else
  API_URL="https://<api-url>"
fi

# Web (alternative: Vercel with NEXT_PUBLIC_API_URL=$API_URL). NEXT_PUBLIC_* are baked at build time.
IMG="${REGION}-docker.pkg.dev/${PROJECT}/cloud-run-source-deploy/${WEB_SVC}:${SHA}"
cat > /tmp/cloudbuild-web.yaml <<YAML
steps:
- name: gcr.io/cloud-builders/docker
  args: ["build","-t","${IMG}","--build-arg","NEXT_PUBLIC_API_URL=${API_URL}","--build-arg","NEXT_PUBLIC_DEMO_ADMIN_TOKEN=${DEMO_TOKEN:-}","."]
images: ["${IMG}"]
YAML
run gcloud builds submit web --config /tmp/cloudbuild-web.yaml
run gcloud run deploy "$WEB_SVC" --image "$IMG" --region "$REGION" --allow-unauthenticated --max-instances 3

echo "Next: set a GCP budget alert (human step); rerun with WEB_ORIGIN=<web url> so CORS allows it; then run scripts/run_scenarios.py --base-url \$API_URL"
