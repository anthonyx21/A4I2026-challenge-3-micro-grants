#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project)}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-micro-grant-ui}"
ADK_AGENT_URL="${ADK_AGENT_URL:-https://cascade-analyst-89073885580.us-central1.run.app}"

echo "Deploying ${SERVICE_NAME} to Cloud Run (project=${PROJECT_ID}, region=${REGION})..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

gcloud run deploy "${SERVICE_NAME}" \
  --source "${SCRIPT_DIR}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --allow-unauthenticated \
  --port 8080 \
  --set-env-vars "ADK_AGENT_URL=${ADK_AGENT_URL}"
