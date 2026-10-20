# ReliefIQ — validation report

This report summarizes verification recorded during implementation on October 20, 2026. It is not a claim that tests or live runs were repeated while preparing this documentation.

## Automated verification

Fourteen backend/chat tests passed. Most API tests use isolated SQLite stores and controlled agent responses. They establish backend behavior under those conditions; the separate live checks below support deployed PostgreSQL and agent integration.

| Coverage | Evidence | Practical conclusion |
|---|---|---|
| Seed parity, reseeding and persistence | `test_exact_seed_and_idempotence` | Original application fields are preserved; edits survive reopening; reseeding keeps edits; stale versions receive 409. |
| Saved memo, input versions, Word and staleness | `test_memo_saves_evidence_versions_and_download` | A successful controlled response saves a memo and snapshot; Word is generated; edits mark the memo stale. |
| Changed agent inputs | `test_wrong_agent_inputs_fail_without_memo` | Mismatched comparison inputs fail and create no successful memo. |
| Budget protection | `test_recommendation_budget_enforced`, `test_budget_changes_respect_pool` | Recommendations fit available funds; round budgets cannot exceed the pool. |
| Reviewer and worker authentication | `test_reviewer_authentication`, `test_internal_worker_requires_task_auth` | Invalid reviewer access is rejected; unauthenticated internal worker requests are rejected. |
| Duplicate jobs and retries | `test_job_claim_prevents_duplicate_execution`, `test_repeated_click_reuses_active_snapshot` | One run is claimed once; repeated active snapshots reuse a run; failed snapshots can start a new run. |
| Interrupted-job recovery and notes | `test_interrupted_job_recovers_as_failure`, `test_note_route_updates_same_application` | Old active jobs become failed when checked; reviewer notes update the same versioned application. |
| Chat provenance, routing and failure | Three tests in `frontend/test_chat.py` | Selected applicants retain simulation labels; chat sessions are separated; unavailable agents do not return canned decisions. |

Recorded additional checks: JavaScript syntax and Git whitespace checks passed. Public-data integration separately recorded 42 agent tests; those are historical results, not another backend test count.

## Deployed verification

| Check | Recorded evidence |
|---|---|
| Complete service | `reliefiq-backend-00001-8df` ready, serving 100% traffic; health returned `database: postgresql`. |
| Five-agent service | `cascade-analyst-00008-wj4`; health listed coordinator plus four specialists and MCP ready. |
| Actual PostgreSQL schema | Direct query confirmed schema version 1, eight applications and saved run/memo tables. Counts increased as additional verification runs completed. |
| Authentication and seed | API returned 401 before login and 200 after; eight cases and original budget settings loaded. |
| Persistent edits and report versions | Reviewer edits survived deployment; browser restored saved report tabs and Word links. Later edits produced a stale-memo flag. |
| Two-applicant live case | Run `25639958-e5e1-44d2-8250-1e8242c2ced7`; memo `e3bcc46d-9231-4c17-8acc-969509ea6bf9`. Both $15,000 requests were below $18,000 cash gaps; no recommendation and $50,000 unallocated. Evidence review: `review_required`. |
| Six-applicant live case | Run `680e6741-04ed-4396-b839-eed69bc115c0`; memo `cd10b8ef-588c-4d49-bada-761356cfd879`. Six evidence records and all seven numbered report sections. |
| Queue callback and Word | Dedicated service's queued callback completed; saved report downloaded as a DOCX document. |
| Public records | 4,571 registry rows and 12 WARN rows loaded; all 232 graph business IDs had exact registry matches. Live Gemini/MCP retrieval retained source dates and county match limits. |

## What these checks do not prove

They do not demonstrate production readiness, comprehensive security, load capacity, regulatory compliance, model accuracy across all cases, or causal benefits from grants. Financial evidence remains simulated and document uploads are absent. Seven report headings do not guarantee all required details appear in every generated paragraph: the preserved example lacks the full GQL text and edge weights in its prose, and the full GQL query is also absent from this saved comparison. Selected structured paths and counts are retained.

Evidence sources: [backend verification](../backend-implementation-status.md), [agent verification history](../../agent/VERIFICATION.md), [backend tests](../../frontend/test_persistence.py), [chat tests](../../frontend/test_chat.py), and the [preserved memo and appendix](example-grant-memo.md).
