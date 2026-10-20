# Backend implementation status

Implemented locally: canonical seed for all eight UI applications; persistent SQLAlchemy storage with PostgreSQL/SQLite support; database-backed dashboard bootstrap and application edits; reviewer notes; saved budget-limited recommendations; budget API; signed reviewer sessions; versioned memo records and immutable input/evidence snapshots; Word export; queued Cloud Tasks worker path and duplicate run claims; dashboard memo generation and restoration.

Removed the backend mock allocation/memo path and browser sample grant memo. Seeded network and scores remain explicitly simulated previews.

Verification: 11 backend/chat tests pass, JavaScript parses, and the local service returns eight database applications. A real call to the deployed Grant Advisor generated and persisted a 6,266-character memo with `compare_applicants` evidence (`status: ok`, `evidence_review: review_required`) for Steel + Lacquer and Impark. The comparison retained $15,000 requests and $18,000 cash gaps, and recommended no funding. Verified local memo ID: `88a9a67b-45ec-4fae-b88e-d89e8e469171`. Word response verified as a DOCX ZIP. An earlier agent HTTP 500 produced a failed run and no memo; a focused comparison prompt resolved the tested path.

Google Cloud provisioning: APIs enabled; PostgreSQL instance creation accepted with operation `9b1b0bd6-2171-4671-a5d7-ab2100000032`. Last authoritative check showed operation RUNNING and instance PENDING_CREATE. Dedicated `reliefiq-backend` account created and Cloud SQL Client binding submitted successfully. Cloud Shell source transfer timed out; its completion is unverified. Do not assume deployment happened.

Still required: inspect transfer and SQL operation state; finish database/user/Secret Manager/queue provisioning; sync latest source; deploy and verify PostgreSQL seeding, edits and queued live memo on Cloud Run; verify rendered edit/report flows; strengthen schema migration/version handling and recovery for interrupted jobs; audit the full proposal acceptance list before marking the goal complete. Default six-applicant live generation remains unverified (the successful live test explicitly selected two).
