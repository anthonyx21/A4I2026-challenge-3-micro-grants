#!/usr/bin/env bash
# One-time administrator setup. No service-account keys are created.
set -euo pipefail
PROJECT_ID=qwiklabs-gcp-04-029c15637557
PROJECT_NUMBER=89073885580
REGION=us-central1
POOL=reliefiq-github
SA="reliefiq-release@${PROJECT_ID}.iam.gserviceaccount.com"
gcloud services enable iamcredentials.googleapis.com sts.googleapis.com artifactregistry.googleapis.com --project="$PROJECT_ID"
if ! gcloud iam service-accounts describe "$SA" --project="$PROJECT_ID" >/dev/null 2>&1; then
 gcloud iam service-accounts create reliefiq-release --display-name='ReliefIQ GitHub release deployer' --project="$PROJECT_ID"
fi
if ! gcloud iam workload-identity-pools describe "$POOL" --location=global --project="$PROJECT_ID" >/dev/null 2>&1; then
 gcloud iam workload-identity-pools create "$POOL" --location=global --display-name='ReliefIQ GitHub releases' --project="$PROJECT_ID"
fi
if ! gcloud iam workload-identity-pools providers describe github --workload-identity-pool="$POOL" --location=global --project="$PROJECT_ID" >/dev/null 2>&1; then
 gcloud iam workload-identity-pools providers create-oidc github --workload-identity-pool="$POOL" --location=global --project="$PROJECT_ID" \
  --issuer-uri=https://token.actions.githubusercontent.com \
  --attribute-mapping='google.subject=assertion.sub,attribute.repository_id=assertion.repository_id,attribute.repository_owner_id=assertion.repository_owner_id,attribute.ref=assertion.ref' \
  --attribute-condition="assertion.repository_id == '1427066686' && assertion.repository_owner_id == '7660271' && assertion.ref == 'refs/heads/release'"
fi
gcloud iam service-accounts add-iam-policy-binding "$SA" --project="$PROJECT_ID" --role=roles/iam.workloadIdentityUser \
 --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/attribute.repository_id/1427066686" --quiet
for SERVICE in cascade-analyst reliefiq-backend; do
 gcloud run services add-iam-policy-binding "$SERVICE" --region="$REGION" --project="$PROJECT_ID" --member="serviceAccount:$SA" --role=roles/run.developer --quiet
done
for RUNTIME in cascade-analyst reliefiq-backend; do
 gcloud iam service-accounts add-iam-policy-binding "${RUNTIME}@${PROJECT_ID}.iam.gserviceaccount.com" --project="$PROJECT_ID" --member="serviceAccount:$SA" --role=roles/iam.serviceAccountUser --quiet
done
if ! gcloud artifacts repositories describe reliefiq-release --location="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
 gcloud artifacts repositories create reliefiq-release --location="$REGION" --repository-format=docker --description='ReliefIQ immutable release images' --project="$PROJECT_ID"
fi
gcloud artifacts repositories add-iam-policy-binding reliefiq-release --location="$REGION" --project="$PROJECT_ID" --member="serviceAccount:$SA" --role=roles/artifactregistry.writer --quiet
printf 'Provider: projects/%s/locations/global/workloadIdentityPools/%s/providers/github\nService account: %s\n' "$PROJECT_NUMBER" "$POOL" "$SA"
