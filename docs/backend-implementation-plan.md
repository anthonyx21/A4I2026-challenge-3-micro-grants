# ReliefIQ backend implementation plan

## Outcome

Keep the existing dashboard experience, replace its hardcoded application data with persistent database records, and let the live Grant Advisor generate a dashboard memo from those same records. Save every memo with its input snapshot and supporting evidence so it can be reopened after a refresh or deployment.

## Current state

- `frontend/server.py` already provides FastAPI endpoints and proxies chat to the deployed ADK agents.
- The browser still defines eight demo applications, financial summaries, document checklists, reviewer notes, budgets and network previews directly in `frontend/static/index.html`.
- The server also imports its own mock data. These two sources can diverge.
- The UI creates a sample memo locally and displays live chat responses as artifacts; these are not durable memo versions.
- `frontend/database.py` and `frontend/seed_data.json` are unfinished, untracked scaffolds. Validate and extend them before treating them as implemented functionality.

## 1. Database and exact seed data

Use Cloud SQL for PostgreSQL in Google Cloud and SQLite for local development. Extend the existing FastAPI backend rather than introducing a second backend.

Store:

| Records | Contents |
|---|---|
| Applications | Existing IDs, business details, requested grants, intended use, review status and record version |
| Financial inputs | Application and tax revenue, quarterly revenue, staffing, quotes, cash gap, assumptions and provenance |
| Document metadata | Required documents, missing items and checklist status; actual uploads are a separate feature |
| Review notes | Application notes, reviewer assignment and timestamps |
| Funding rounds | Total pool, committed funds, available round budget and recommended allocations |
| Analysis runs | Status, immutable input snapshot, agent/tool evidence, timestamps and failure details |
| Memo versions | Application and run references, content, authoring agent and creation time |

Extract the existing browser records into one canonical seed file. Preserve the eight applications and all displayed mock values, including the $150,000 pool, $100,000 committed and $50,000 round budget. Preserve preview network data separately from live BigQuery graph evidence.

Mark the seed as simulated: real business identifiers do not make invented owners, financials, document claims or network links verified. Preserve requested grant and cash gap as separate fields—for example, Steel + Lacquer requests $15,000 while its mock text describes an $18,000 gap. Where the mock does not specify a gap, record any assumption explicitly.

Use versioned migrations and an idempotent seed command. Seed only missing records; rerunning it must not overwrite reviewer edits. Verify every original field against the seeded records.

## 2. Database-backed API

Add or adapt these routes:

| Endpoint | Purpose |
|---|---|
| `GET /api/bootstrap` | Load dashboard applications, budgets, reviewer state and saved memo summaries |
| `GET /api/applications/{id}` | Read the current application and supporting inputs |
| `PATCH /api/applications/{id}` | Save validated edits with optimistic version checks |
| `POST /api/applications/{id}/notes` | Save reviewer notes |
| `PATCH /api/funding-rounds/{id}` | Update budget settings with validation |
| `POST /api/analysis-runs` | Start an agent comparison using selected database applications |
| `GET /api/analysis-runs/{id}` | Return running, complete or failed status and evidence |
| `POST /api/applications/{id}/memos` | Generate a memo from the selected application and comparison context |
| `GET /api/applications/{id}/memos` | List saved versions |
| `GET /api/memos/{id}` | Read a saved memo and its evidence references |
| `GET /api/memos/{id}/download` | Download the memo as a Word document |

Retain `/api/chat`, but build its application context from database records. Consolidate existing mock allocation/detail endpoints so the browser and agent cannot read different application datasets.

Reject invalid amounts and stale edits. Separate recommended allocations from approved or paid grants. Require appropriate authorization for shared edits and memo generation; the existing demo login/client UUID is not authentication.

## 3. Agent-driven dashboard memo

The backend loads the selected application, comparison shortlist, budget and assumptions from the database. It saves their versions as an immutable snapshot, then invokes the existing ADK Grant Advisor.

The agent uses the same application inputs plus live cascade, neighborhood, public-record and evidence-review tools. BigQuery remains the source for analytical evidence; PostgreSQL stores application and workflow data.

Persist both the generated seven-part grant memo and the structured tool results. Validate that the evidence refers to the requested application IDs and funding inputs. Clearly distinguish simulated financial inputs, modeled graph effects and sourced public records.

The memo should cover the recommendation, named cascade effects, funding rationale, conditions and missing evidence, alternatives, modeling limitations and neighborhood context, following the existing Grant Advisor instructions. A requested grant below the stated cash gap must not silently become a fully funded stabilization scenario.

Use a durable background job with polling rather than relying on a long browser request. Record failures, support safe retries and prevent duplicate jobs on repeated clicks. A failed run must not create a successful memo or substitute a local mock. An analysis that finds no feasible allocation can still produce an honest memo explaining that result.

MCP is optional for document creation: ADK already provides the agent orchestration. If implementing the previously proposed MCP report component, give it the saved memo and evidence to render the report, then save its artifact reference. Otherwise, the backend can export Word directly without claiming an MCP integration.

## 4. Frontend integration

- Load applications and budget values from `/api/bootstrap`; remove their duplicate JavaScript definitions.
- Save application edits, notes and recommendation state through the API.
- Replace locally generated grant memos with a **Generate Dashboard Memo** action.
- Show progress and recoverable errors while the agent runs.
- Display the saved memo in the existing report panel, with version, timestamp, input provenance and Word download.
- Restore saved reports on refresh and indicate when newer application edits make an older memo stale.
- Label retained mock scores and network illustrations as seeded previews. Show live agent evidence distinctly.

## 5. Deployment

Provision Cloud SQL PostgreSQL, migrations, database credentials in Secret Manager and a backend service account. Give it only the necessary Cloud SQL, secret and agent-invocation access. Connect the existing Cloud Run frontend/backend service to Cloud SQL; keep database credentials server-side.

Deploy the job worker and configure the queue, timeouts and retry policy. Verify Cloud SQL and required APIs are available in the Qwiklabs project; if the lab restricts them, document the blocker and evaluate an available durable database before changing the architecture. Configure service authentication, logs and database backups appropriate to the project lifetime.

## 6. Acceptance checks

1. All eight applications and their original displayed values appear from the seeded database.
2. Reseeding preserves edited records; application changes survive a process restart and deployment.
3. The dashboard and agent use the same saved versions and round budget.
4. A generated memo contains live tool evidence, is saved with its snapshot, reopens after refresh and downloads as Word.
5. Editing a financial input changes the next run's snapshot while preserving earlier memo versions.
6. Agent failures and duplicate clicks produce clear, consistent run states without fabricated reports.
7. Stale writes, unauthorized changes and over-budget recommendations are handled correctly.
8. Seeded previews and public/modeled evidence retain explicit provenance throughout the UI and report.

## Delivery order

Implement and verify the database, migration and seed first; then the API and dashboard reads/edits; then durable agent runs and memo export; finally deploy and run the acceptance checks against Google Cloud.
