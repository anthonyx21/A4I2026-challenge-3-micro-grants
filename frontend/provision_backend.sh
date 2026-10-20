#!/usr/bin/env bash
set -euo pipefail
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-qwiklabs-gcp-04-029c15637557}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
DB_INSTANCE="${DB_INSTANCE:-reliefiq-db}"
BACKEND_SA="reliefiq-backend@${PROJECT_ID}.iam.gserviceaccount.com"
CONNECTION="${PROJECT_ID}:${REGION}:${DB_INSTANCE}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
gcloud sql databases create reliefiq --instance="$DB_INSTANCE" --project="$PROJECT_ID"
RELIEFIQ_DB_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
gcloud sql users create reliefiq --instance="$DB_INSTANCE" --password="$RELIEFIQ_DB_PASSWORD" --project="$PROJECT_ID"
RELIEFIQ_SECRET_FILE="$(mktemp)"
chmod 600 "$RELIEFIQ_SECRET_FILE"
trap 'rm -f "$RELIEFIQ_SECRET_FILE"' EXIT
printf 'postgresql+psycopg://reliefiq:%s@/reliefiq?host=/cloudsql/%s' "$RELIEFIQ_DB_PASSWORD" "$CONNECTION" > "$RELIEFIQ_SECRET_FILE"
gcloud secrets create reliefiq-database-url --data-file="$RELIEFIQ_SECRET_FILE" --project="$PROJECT_ID"
unset RELIEFIQ_DB_PASSWORD
gcloud secrets add-iam-policy-binding reliefiq-database-url --member="serviceAccount:$BACKEND_SA" --role=roles/secretmanager.secretAccessor --project="$PROJECT_ID" --quiet
printf '%s' "${REVIEWER_PASSWORD:-demopassword}" > "$RELIEFIQ_SECRET_FILE"
gcloud secrets create reliefiq-reviewer-password --data-file="$RELIEFIQ_SECRET_FILE" --project="$PROJECT_ID"
gcloud secrets add-iam-policy-binding reliefiq-reviewer-password --member="serviceAccount:$BACKEND_SA" --role=roles/secretmanager.secretAccessor --project="$PROJECT_ID" --quiet
gcloud tasks queues create reliefiq-memos --location="$REGION" --max-concurrent-dispatches=1 --max-attempts=1 --project="$PROJECT_ID"
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$BACKEND_SA" --role=roles/cloudtasks.enqueuer --quiet
BACKEND_SA="$BACKEND_SA" CLOUD_SQL_CONNECTION="$CONNECTION" "$SCRIPT_DIR/deploy.sh"
