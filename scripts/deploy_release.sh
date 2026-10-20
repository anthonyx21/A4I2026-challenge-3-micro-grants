#!/usr/bin/env bash
# Deploy immutable release images without routing traffic until checks pass.
set -euo pipefail
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-qwiklabs-gcp-04-029c15637557}"
REGION="${DEPLOY_REGION:-us-central1}"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/${IMAGE_REPOSITORY:-reliefiq-release}"
RELEASE_SHA="${RELEASE_SHA:-$(git rev-parse HEAD)}"
RELEASE_TAG="release-${RELEASE_SHA:0:12}"
BACKEND_URL="https://reliefiq-backend-89073885580.us-central1.run.app"
AGENT_URL="https://cascade-analyst-89073885580.us-central1.run.app"
AGENT_REVISION="cascade-analyst-${RELEASE_SHA:0:12}"
BACKEND_REVISION="reliefiq-backend-${RELEASE_SHA:0:12}"

gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
docker build -t "$REGISTRY/agents:$RELEASE_SHA" ./agent
docker build -t "$REGISTRY/backend:$RELEASE_SHA" ./frontend
docker push "$REGISTRY/agents:$RELEASE_SHA"
docker push "$REGISTRY/backend:$RELEASE_SHA"

# A rerun of the same commit reuses its existing immutable revision.
if ! gcloud run revisions describe "$AGENT_REVISION" --region="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud run deploy cascade-analyst --image="$REGISTRY/agents:$RELEASE_SHA" \
    --project="$PROJECT_ID" --region="$REGION" --no-traffic --tag="$RELEASE_TAG" --revision-suffix="${RELEASE_SHA:0:12}" \
    --service-account="cascade-analyst@${PROJECT_ID}.iam.gserviceaccount.com" \
    --memory=2Gi --cpu=2 --concurrency=8 --max-instances=3 --min-instances=0 --timeout=300 \
    --set-env-vars="GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=global,AGENT_MODEL=gemini-2.5-flash,BQ_DATASET=a4i_econ,BQ_GRAPH=CascadeEconomy,BQ_LOCATION=US,CORRIDOR=Central Market,TOOLBOX_URL=http://127.0.0.1:5000" --quiet
fi
if ! gcloud run revisions describe "$BACKEND_REVISION" --region="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud run deploy reliefiq-backend --image="$REGISTRY/backend:$RELEASE_SHA" \
    --project="$PROJECT_ID" --region="$REGION" --no-traffic --tag="$RELEASE_TAG" --revision-suffix="${RELEASE_SHA:0:12}" \
    --service-account="reliefiq-backend@${PROJECT_ID}.iam.gserviceaccount.com" \
    --add-cloudsql-instances="${PROJECT_ID}:${REGION}:reliefiq-db" \
    --port=8080 --timeout=600 --memory=512Mi --max-instances=3 \
    --set-secrets='DATABASE_URL=reliefiq-database-url:latest,REVIEWER_PASSWORD=reliefiq-reviewer-password:latest' \
    --set-env-vars="ADK_AGENT_URL=${AGENT_URL},REQUIRE_REVIEWER_LOGIN=true,PUBLIC_BACKEND_URL=${BACKEND_URL},MEMO_TASK_QUEUE=projects/${PROJECT_ID}/locations/${REGION}/queues/reliefiq-memos" --quiet
fi
# Ensure tags exist on reruns as well as new releases.
gcloud run services update-traffic cascade-analyst --set-tags="${RELEASE_TAG}=${AGENT_REVISION}" --region="$REGION" --project="$PROJECT_ID" --quiet
gcloud run services update-traffic reliefiq-backend --set-tags="${RELEASE_TAG}=${BACKEND_REVISION}" --region="$REGION" --project="$PROJECT_ID" --quiet
# Use JSON parsing instead of relying on gcloud list-filter expression semantics.
export RELEASE_TAG
export RELIEFIQ_AGENT_CANDIDATE="$(gcloud run services describe cascade-analyst --region="$REGION" --project="$PROJECT_ID" --format=json | python3 -c 'import json,os,sys; print(next(t["url"] for t in json.load(sys.stdin)["status"]["traffic"] if t.get("tag")==os.environ["RELEASE_TAG"]))')"
export RELIEFIQ_BACKEND_CANDIDATE="$(gcloud run services describe reliefiq-backend --region="$REGION" --project="$PROJECT_ID" --format=json | python3 -c 'import json,os,sys; print(next(t["url"] for t in json.load(sys.stdin)["status"]["traffic"] if t.get("tag")==os.environ["RELEASE_TAG"]))')"
python3 - <<'PY'
import json, os, urllib.request, time
for name, base in [('agents', os.environ['RELIEFIQ_AGENT_CANDIDATE']), ('backend', os.environ['RELIEFIQ_BACKEND_CANDIDATE'])]:
    for attempt in range(12):
        try:
            with urllib.request.urlopen(base+'/api/health', timeout=30) as r: data=json.load(r)
            assert data['status']=='ok'
            if name=='backend': assert data['database']=='postgresql'
            else:
                assert data['mcp']=='ready'
                assert set(data['agents'])=={'corridor_coordinator','grant_advisor','cascade_analyst','evidence_reviewer','neighborhood_context'}
            print('CANDIDATE_VERIFIED', name, base)
            break
        except Exception:
            if attempt==11: raise
            time.sleep(5)
PY
# Both candidates passed. Promote agents first; then promote their frontend client.
gcloud run services update-traffic cascade-analyst --to-revisions="${AGENT_REVISION}=100" --project="$PROJECT_ID" --region="$REGION" --quiet
gcloud run services update-traffic reliefiq-backend --to-revisions="${BACKEND_REVISION}=100" --project="$PROJECT_ID" --region="$REGION" --quiet
printf 'Released %s\nDashboard: %s\nAgents: %s\n' "$RELEASE_SHA" "$BACKEND_URL" "$AGENT_URL"
