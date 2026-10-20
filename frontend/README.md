# ReliefIQ dashboard backend

The existing FastAPI service serves the dashboard, stores application data and calls the deployed ADK agents. Eight original UI applications are seeded from `seed_data.json`; their financials, owners, document claims, scores and illustrated network remain simulated. Public business IDs do not verify those scenario details.

## Local development

```bash
pip install -r frontend/requirements.txt
RELIEFIQ_DATA_DIR=./.local-data python -m uvicorn frontend.server:app --port 8080 --reload
```

SQLite persists locally. Set `DATABASE_URL` to a SQLAlchemy PostgreSQL URL to use PostgreSQL. Cloud Run requires an explicit database URL. Run `python -m frontend.migrate --seed` to apply the initial versioned schema explicitly. Schema version 1 is also applied on first database access; reseeding preserves edits. The application JSON retains the original financial summaries, document metadata, network previews and notes. Analysis runs and memo versions are separate records with application references.

The challenge reviewer password defaults to `demopassword`; enable signed-cookie enforcement locally with `REQUIRE_REVIEWER_LOGIN=true` and set `REVIEWER_PASSWORD`. This shared reviewer account is intended for the challenge demonstration, not municipal production authentication.

## Dashboard memo

Open an application and select **Generate Dashboard Memo**, or ask for a grant memo in chat. The backend snapshots saved applications, grant requests, cash gaps, assumptions, versions and round budget. The existing Grant Advisor uses live BigQuery cascade and public evidence. Its comparison inputs are checked against the saved snapshot before the memo and evidence are stored. Failed runs never create a successful report.

The comparison tool supports 2–6 applicants. The default shortlist contains the selected application plus five others; callers can explicitly provide `applicant_ids`. A $15,000 request with an $18,000 gap remains an infeasible full-gap scenario. Earlier memo versions retain their original snapshot after edits. `GET /api/memos/{id}` reports whether versions are stale; `/download` exports Word.

Cloud deployment uses Cloud Tasks for memo generation, with one concurrent job and explicit user retry after failures. The browser polls saved run status. Without `MEMO_TASK_QUEUE`, local generation runs in the request.

## Google Cloud

Enable SQL Admin, Secret Manager and Cloud Tasks APIs. Create PostgreSQL 15 instance `reliefiq-db` in `us-central1`, plus the `reliefiq-backend` service account with Cloud SQL Client access. Then run:

```bash
./frontend/provision_backend.sh
```

This first-time provisioning script creates the database/user, stores the database URL and reviewer password in Secret Manager, grants access, creates the queue and deploys. It is a first-time script; use `./frontend/deploy.sh` for later deployments. Do not rerun first-time credential creation against existing resources.

Cloud Run connects to the Cloud SQL socket and receives secrets server-side. Cloud Tasks calls a protected internal worker route. Deployment currently uses the public challenge agent URL; if agent access is restricted, configure service-to-service identity authentication before changing that service's policy.

## Verification

```bash
pytest -q frontend/test_persistence.py frontend/test_chat.py
```

Tests cover field-by-field seed parity, idempotence, durable edits, version conflicts, memo persistence/download/staleness, rejection of changed agent inputs, budget limits, reviewer login, live chat routing and failure behavior.
