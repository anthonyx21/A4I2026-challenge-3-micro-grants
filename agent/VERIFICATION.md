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
