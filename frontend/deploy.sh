#!/usr/bin/env bash
set -euo pipefail
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-qwiklabs-gcp-04-029c15637557}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-reliefiq-backend}"
ADK_AGENT_URL="${ADK_AGENT_URL:-https://cascade-analyst-89073885580.us-central1.run.app}"
BACKEND_SA="${BACKEND_SA:-reliefiq-backend@${PROJECT_ID}.iam.gserviceaccount.com}"
CLOUD_SQL_CONNECTION="${CLOUD_SQL_CONNECTION:-${PROJECT_ID}:${REGION}:reliefiq-db}"
PUBLIC_BACKEND_URL="${PUBLIC_BACKEND_URL:-https://reliefiq-backend-89073885580.us-central1.run.app}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
gcloud run deploy "$SERVICE_NAME" --source "$SCRIPT_DIR" --project "$PROJECT_ID" --region "$REGION" \
  --allow-unauthenticated --port 8080 --timeout 600 --memory 512Mi --max-instances 3 \
  --service-account "$BACKEND_SA" --add-cloudsql-instances "$CLOUD_SQL_CONNECTION" \
  --set-secrets 'DATABASE_URL=reliefiq-database-url:latest,REVIEWER_PASSWORD=reliefiq-reviewer-password:latest' \
  --set-env-vars "ADK_AGENT_URL=${ADK_AGENT_URL},REQUIRE_REVIEWER_LOGIN=true,PUBLIC_BACKEND_URL=${PUBLIC_BACKEND_URL},MEMO_TASK_QUEUE=projects/${PROJECT_ID}/locations/${REGION}/queues/reliefiq-memos" --quiet
