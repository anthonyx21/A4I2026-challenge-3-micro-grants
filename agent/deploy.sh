#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
DEPLOY_PROJECT="${GOOGLE_CLOUD_PROJECT:-qwiklabs-gcp-04-029c15637557}"
DEPLOY_REGION="${DEPLOY_REGION:-us-central1}"
RUNTIME_ACCOUNT="cascade-analyst@${DEPLOY_PROJECT}.iam.gserviceaccount.com"
# Requires the runtime account to exist with BigQuery jobUser, dataset READER,
# and aiplatform.user. Never place login passwords in this container's environment.
gcloud run deploy cascade-analyst \
  --source=. --project="$DEPLOY_PROJECT" --region="$DEPLOY_REGION" \
  --service-account="$RUNTIME_ACCOUNT" --allow-unauthenticated \
  --memory=2Gi --cpu=2 --concurrency=8 --max-instances=3 --min-instances=0 \
  --timeout=300 \
  --set-env-vars="GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=${DEPLOY_PROJECT},GOOGLE_CLOUD_LOCATION=global,AGENT_MODEL=gemini-2.5-flash,BQ_DATASET=a4i_econ,BQ_GRAPH=CascadeEconomy,BQ_LOCATION=US,CORRIDOR=Central Market,TOOLBOX_URL=http://127.0.0.1:5000" \
  --quiet
