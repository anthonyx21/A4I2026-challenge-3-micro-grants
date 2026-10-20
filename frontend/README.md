# Central Market Micro-Grant Relief Advisor — Frontend UI

Clean 2-panel web UI for **Challenge 3 (Track 1: Main Street Relief)** connected to the live Cloud Run ADK agents (`grant_advisor` and `cascade_analyst`) at `https://cascade-analyst-89073885580.us-central1.run.app/`.

---

## 1. Run Locally

```bash
pip install -r frontend/requirements.txt
python -m uvicorn frontend.server:app --host 127.0.0.1 --port 8080 --reload
```

Open **`http://localhost:8080`**.

---

## 2. Build & Deploy to Google Cloud Run

Both the repo root ([Dockerfile](file:///c:/Projects/A4I2026-challenge-3-micro-grants/Dockerfile)) and `frontend/` ([frontend/Dockerfile](file:///c:/Projects/A4I2026-challenge-3-micro-grants/frontend/Dockerfile)) are configured for 1-command Cloud Build + Cloud Run deployment.

### Option A: One-Line `gcloud run deploy` (from repo root or `frontend/`)

Run in **Google Cloud Shell** (or any terminal authenticated with `gcloud` for project `qwiklabs-gcp-04-029c15637557`):

```bash
gcloud run deploy micro-grant-ui \
  --source ./frontend \
  --project qwiklabs-gcp-04-029c15637557 \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --set-env-vars "ADK_AGENT_URL=https://cascade-analyst-89073885580.us-central1.run.app"
```

### Option B: Run the Deploy Script

```bash
chmod +x frontend/deploy.sh
./frontend/deploy.sh
```
