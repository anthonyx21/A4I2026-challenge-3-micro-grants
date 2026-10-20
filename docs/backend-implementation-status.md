# ReliefIQ backend verification

## Implemented

The FastAPI dashboard uses persistent SQLAlchemy storage with Cloud SQL PostgreSQL in Google Cloud and SQLite locally. The canonical seed preserves all eight original UI applications and budget settings. Financial summaries, document checklists, reviewer notes, assignments, scores and network illustrations remain labeled simulated.

Database-backed routes load/edit applications, save reviewer notes, enforce budget-limited recommendations, update round budget, start analyses, save immutable run snapshots and evidence, list/read memo versions, flag stale inputs and export Word. Signed cookies protect the shared challenge reviewer session. Cloud Tasks invokes an authenticated worker; active snapshots are reused and job claims prevent duplicate execution. Interrupted jobs fail after a 30-minute recovery deadline so users can retry.

The dashboard loads its data from the API, saves financial edits, generates live Grant Advisor memos, restores saved versions after refresh and offers Word download. The local sample grant memo and separate backend mock allocation path were removed. ADK compares saved application inputs with live BigQuery cascade/public/neighborhood evidence. MCP report export remains proposed; Word export is implemented in the backend.

## Verified

- Fourteen backend/chat tests pass, including field-by-field seed parity, persistence/reseed safety, stale writes, budget constraints, authenticated reviewer access, protected worker access, duplicate-run claims, interrupted-job recovery, memo evidence validation and Word export. JavaScript syntax passes.
- Local live tests succeeded for a two-applicant no-feasible-funding scenario and the default six-applicant scenario.
- Cloud SQL instance `reliefiq-db` is RUNNABLE. Secret Manager stores backend credentials, and `reliefiq-backend` is the dedicated runtime service account.
- Previous verified Cloud Run URL: https://micro-grant-ui-89073885580.us-central1.run.app . Revision `micro-grant-ui-00006-qtc` was verified ready and serving 100% of traffic before the final schema update deployment.
- Deployed health reports PostgreSQL. Unauthenticated API access receives 401; challenge reviewer login succeeds. All original seed fields are preserved, with added reviewer notes.
- Queued live run `b2d8a619-a163-4e37-8cdc-92ac5e817883` completed, saving memo `5aceb3e3-b997-429b-8a04-ec39e1b5c76a` and its exact input versions/evidence. Its Word download works.
- On the latest verified revision, default six-applicant run `680e6741-04ed-4396-b839-eed69bc115c0` completed and saved memo `cd10b8ef-588c-4d49-bada-761356cfd879`, containing all seven required sections.
- Deployed browser restored saved reports and download links, exposed memo/edit actions and saved a reviewer-note edit. The earlier memo correctly became stale. Database records and memos survived deployment.

## Final deployment verification

Schema/version and recovery update `e47df6f` deployed as `micro-grant-ui-00008-69t`. Direct PostgreSQL checks proved schema version 1, eight applications, two analysis runs and two memo versions. Another deployment then replaced the service with older mock revision `micro-grant-ui-00009-k7v`. The backend is deployed separately as `reliefiq-backend`, with its own Cloud Tasks callback URL, to avoid competing deployments. Revision `reliefiq-backend-00001-8df` is ready and serving 100% of traffic. Health, login, eight PostgreSQL application records, saved memos and branded browser report restoration are verified. Queued live callback test completed: run `25639958-e5e1-44d2-8250-1e8242c2ced7` saved memo `e3bcc46d-9231-4c17-8acc-969509ea6bf9`. The application now has two saved versions, the database has three memos in total, the new memo matches current input versions and has all seven numbered sections, and Word download works.

## Practical scope

The reviewer account is a shared challenge-demo account, not individual municipal authentication. Document records are metadata and simulated claims; actual uploads are not implemented. BigQuery graphs/public records inform the agents; PostgreSQL holds applications and workflow state. The default comparison shortlist includes six of eight applications, matching the existing agent tool limit; it must not be described as an all-applicant optimization. Recommendations require human review and do not disburse funds. Cloud Tasks is configured for one concurrent dispatch and explicit user retry after failures.
