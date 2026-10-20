# Verification — October 20, 2026

- Local Python 3.12: seven evidence/MCP/query tests passed; dependency check and syntax checks passed.
- ADK tool declarations successfully generated for `search_businesses` and `analyze_cascade`.
- Live setup validated 232 unique business keys and 994 unique supply edge keys/references in Central Market.
- Created `qwiklabs-gcp-04-029c15637557.a4i_econ.CascadeEconomy` metadata, preserving tables and existing graphs. An actual two-hop GQL MATCH completed; no reservation change was required.
- Google's Toolbox v1.14.0 binary was checked against its published SHA256. All runtime graph queries passed through MCP Streamable HTTP to Toolbox.
- Live supply-disruption analysis of Steel + Lacquer (`1026779-04-151`): 23 unique reachable businesses, 10 direct and 13 at two hops. Cutoff 0.01: seven reachable, four direct and three at two hops. Sixteen endpoints removed; 30.4% retained. This is modeled exposure, not measured transactions or predicted closures.
- Live reverse customer-loss traversal succeeded with 15 unique endpoints. Unknown business ID returns `not_found`; Toolbox's zero-row string response is handled explicitly.
- Live Gemini 2.5 Flash ADK run successfully called search and analysis tools, reported the same counts and limitations, and passed `--verify-tools`.
- ADK development UI on Cloud Shell port 8080 returned HTTP 200; `/list-apps` returned `["cascade_analyst"]`.

Remote working copy: `~/agents-for-impact/cascade-analyst-build/agent`. Grant Advisor is now implemented below. Real applicant financial evidence, a custom UI and submission assets remain outside this initial build.

## Cloud Run deployment

- Service: `cascade-analyst`, project `qwiklabs-gcp-04-029c15637557`, region `us-central1`.
- URL: https://cascade-analyst-89073885580.us-central1.run.app
- Ready revision: `cascade-analyst-00002-k29`. Agent and localhost-only MCP Toolbox run in the same container.
- Runtime identity: `cascade-analyst@qwiklabs-gcp-04-029c15637557.iam.gserviceaccount.com`, granted BigQuery jobUser, READER on `a4i_econ`, and Vertex AI user.
- Uses Google authentication; service IAM has no public invoker binding. Login username in the workspace `.env` matches the authenticated deployment account. Password was not copied into the image or runtime environment.
- Authenticated live model/API verification completed on the first revision: successful search and cascade tool responses, with 23 baseline and seven filtered endpoints. Seven local tests still pass.
- Updated the health route to `/api/health` after the Google ingress returned a 404 for `/healthz` while `/list-apps` and `/dev-ui/` worked.
- Final verification of revision `cascade-analyst-00002-k29` passed health, agent discovery and successful live model/MCP tool responses (`CLOUD_RUN_VERIFIED 23 7`).
- Authenticated Cloud Shell proxy on port 8081 verified agent discovery. Browser chat UI loads and selects `cascade_analyst`.
- Scales to zero; two CPUs, 2 GiB memory, concurrency eight, maximum three instances, request timeout 300 seconds. Chat sessions are ephemeral in-memory sessions.

## Grant Advisor — implemented and deployed

- Added Python ADK `grant_advisor`, custom `compare_applicants`, deterministic portfolio allocation, and callable `cascade_analyst` AgentTool for specialist follow-ups. Both agents share existing read-only MCP/BigQuery access.
- Twenty-three local tests passed, including budget feasibility, exact cents, overlap deduplication, full-gap policy, provenance validation, sensitivity changing the choice, and graph outage blocking recommendations. ADK comparison schema and remote agent import succeeded.
- Latest ready revision: `cascade-analyst-00004-dzf`, serving both agents at the existing authenticated service URL. `/api/health` reports both agents and MCP ready; `/list-apps` returns both.
- Live Gemini run called `compare_applicants` successfully against real BigQuery graph data. Final verification exited zero and wrote a simulated grant memo plus structured trace to remote ignored `reports/`.
- Explicitly synthetic demo: USD 5,000 budget; two applicants each assigned a fictional USD 5,000 gap/request; 30-day assumed operating horizon. Steel + Lacquer: baseline 23, filtered seven. Impark 0314: baseline 24, filtered zero. Recommended simulated grant: Steel + Lacquer USD 5,000, unallocated zero; runner-up Impark. Removing weak-link filtering changes the preferred applicant to Impark.
- These are invented financial scenarios attached to real identities, not evidence of distress or requests. Counts describe modeled reachability; grant benefits are conditional on unverified operating assumptions. This rule omits equity, cultural value, substitution and causal effects.
- Browser chat UI loaded with `grant_advisor` selected through port 8081. One JavaScript asset returned a transient proxy 500; reloading resolved it.
- Usage, required applicant inputs and live verification command are recorded in `RUNBOOK.md`; reproducible financial scenario is `grant_advisor/demo.json`.

## Evidence Reviewer and Neighborhood Context — October 20, 2026

- Added two standalone ADK agents plus Grant Advisor specialist tools: `evidence_reviewer` and `neighborhood_context`. Every comparison now includes deterministic `evidence_review`; an error blocks the advisor recommendation. Draft reviews additionally recompute live graph evidence and screen wording.
- Thirty-four local tests passed. New coverage checks money reconciliation, recipient and exposure identities, simulation labels, conservative phrase screening, fractional worker allocations, duplicate block/business edges, missing demographic matches, invalid rates and truncation. ADK tool declarations and all four agent imports passed.
- Cloud Run revision `cascade-analyst-00005-8qb` serves all four agents under the existing authenticated service. Health reports MCP ready; API discovery and browser app selector list all four. Existing runtime identity and read-only dataset permissions suffice; no new tables or graph metadata were created.
- Live Gemini/MCP Neighborhood Context call for Blick Art Materials LLC (`1080659-07-161`) succeeded: 153.4718253968254 modeled worker allocation, 12 linked workplace blocks, 6,608 jobs in those blocks, seven dataset demographic tracts, no missing linked demographic matches. These are not business employment or actual visits.
- Live Evidence Reviewer call recomputed the two-applicant simulated USD 5,000 scenario. Consistency checks passed, status `review_required`, `approval_ready=false`. It flagged simulated inputs, sensitive choice, causal wording, approval wording, unaudited documents and modeled relationships. Draft wording "protects 7 businesses. Grant approved" was corrected and qualified.
- `verify_specialists.py` completed with `SPECIALISTS_VERIFIED`; traces are saved remotely in ignored `reports/neighborhood_context-verification.json` and `reports/evidence_reviewer-verification.json`.
- Neighborhood context uses two additional fixed read-only Toolbox SQL queries. Worker links join by block ID; demographic matches use padded 11-character tract IDs. Tract rates remain fractions with distinct source denominators; no corridor aggregate or demographic funding score is inferred.
- Integrated Grant Advisor live verification passed on the same revision, retaining the seven-versus-zero filtered demo comparison and returning automatic `evidence_review.status=review_required`, with consistency checks passed and no approval clearance.
