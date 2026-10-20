# Frontend review against Challenge 3

Reviewed October 20, 2026, on repository commit `26eba01`. Scope: frontend source, the challenge README, existing agent contracts and verification notes, local execution of frontend functions, and one live frontend-backend-to-ADK request. No frontend deployment or visual screenshot inspection was performed. No application code was changed.

## Assessment

The two-panel applicant queue and contextual chat are appropriate for Main Street relief, but this is currently a hybrid prototype: allocations, metrics and downloadable memo content come from hard-coded mock fixtures, while chat can call the real deployed agents. The queue and chat do not share one authoritative decision result. This threatens technical execution and rigor more than additional visual polish would improve craft.

The challenge requires a defended funding case: named recipient/address/amount, named downstream paths with hops and intensity, the actual traversal, runner-up, intervention assumptions, evidence provenance and neighborhood context. It also asks for an actual allocation-outcome equity audit. The frontend has concepts for these but several are hard-coded, inaccessible from the current UI, or inconsistent with the live backend.

## Findings, in priority order

1. **Critical: hard-coded evidence is represented as verified or measured.** `frontend/mock_data.py:1682` replaces fixture applicant IDs and names with live registry identities while retaining mock cascades, loan records, distress scores, tracts and decision narratives. Several overrides label financial gaps `verified`, with no supporting documents or query. The context sent to the model includes these labels (`frontend/server.py:442`). Fabricated historical charge-off observations and static validation/equity claims remain exposed through APIs and fallback prose (`frontend/mock_data.py:1578`, `frontend/mock_data.py:1663`, `frontend/server.py:570`). Existing project verification established four matched EXEMPT loans without charge-offs; the frontend instead claims nine loans and three charge-offs. Distinguish historical checked project data from current runtime queries: this review did not re-query loan tables. Relabel all invented financial/loan/impact fixtures as synthetic and never merge them into asserted facts about real businesses.

2. **Critical: failed live requests silently produce an apparent graph answer.** On a deliberately simulated connection failure, `/api/chat` returned a canned three-charge-off backtest and source `Central Market Graph Engine (a4i_econ.LocalEconomy)` (`frontend/server.py:629`). There was no offline/synthetic status. The initial chat connection badge is also unconditional (`frontend/static/index.html:164`). An unavailable agent should return an explicit failure or a clearly separate synthetic-demo result. A function-call name alone does not prove a successful tool response.

3. **High: two incompatible allocation policies.** `/api/allocate` ranks mock fragility and weighted edges; the ADK Grant Advisor uses supplied full-gap feasibility and deduplicated live filtered reachability. Frontend partial grants keep full assumed impact even when below the gap (`frontend/server.py:330`). At a USD 24,000 budget, local execution funded Orpheum USD 18,000 and Sumfer USD 6,000 against a USD 15,000 gap. Portfolio reach sums applicant counts instead of taking a union (`frontend/server.py:349`). The chat sends only the first five of eleven queue applicants, irrespective of officer selection, and ignores the UI equity carve-out and weighting choices in the comparison inputs. Render queue, KPIs, chat and memo from the same structured comparison report, with an explicit shortlist.

4. **High: unsupported impact and sensitivity calculations.** `frontend/server.py:99` multiplies two-hop weights by 4; the stress case scales weights by 0.82 and removes one endpoint without a node-specific re-traversal. Hard-coded closure probabilities and fragility generate “expected business-equivalents protected.” The memo claims the applicant remains ahead at a 20-point risk reduction without rerunning the allocation (`frontend/server.py:255`). Assumptions are permissible under the challenge, but must be explicitly supplied or labeled synthetic, defended and tested. They are not calibrated forecasts. The displayed query uses `LocalEconomy`, while the current agents query `CascadeEconomy`; a query string is not evidence that the frontend executed it.

5. **High: equity control is mislabeled and the audit is static.** The 15% carve-out actually selects one eligible leaf and spends its full USD 8,000 ask (`frontend/server.py:303`). Local execution produced 40% of a USD 20,000 budget, 16% of USD 50,000 and 5.3% of USD 150,000. `EQUITY_AUDIT_SUMMARY` is fixture data, not an audit of the actual chosen portfolio, and the current page exposes no audit panel. Compute funded industry shares and demographic context from the actual allocation and source data. Do not infer valid population-weighted corridor rates without the required denominators.

6. **High: shared chat state and unsafe HTML rendering.** Every visitor uses `ui_grant_officer` and the same cached session per agent (`frontend/server.py:61`, `frontend/server.py:439`), allowing cross-user state mixing. `formatMarkdown` directly embeds unescaped model text into `innerHTML` (`frontend/static/app.js:240`, `frontend/static/app.js:261`); HTML from a model response is not sanitized. Isolate user/session state and sanitize Markdown output or render safe text. The deployment script allows public frontend access without application identity or explicit rate limits. Review this against the intended internal-officer audience and model-cost exposure.

7. **Medium: key challenge evidence is not surfaced.** The page is primarily queue plus chat; the detail API's traversal and memo are not connected to visible graph/evidence or export controls. Evidence Reviewer and Neighborhood Context are absent from the selector. There is no editable financial intake, operational horizon, weak-edge sensitivity cutoff or supplied-document provenance workflow. Add a compact live path/evidence view, reviewer findings, neighborhood context and memo export before adding more agents.

8. **Medium: error, timeout and request handling.** Allocation inputs have no meaningful server-side budget/range/enum constraints. Fetch handlers do not check `res.ok`; preset buttons remain usable during a chat request, and overlapping refreshes can overwrite newer state. Chat times out at 90 seconds, below the 240-second comparison bound and 300-second Cloud Run request limit. Surface errors, align bounded timeouts and prevent stale or concurrent state updates. Dependency versions are unpinned and Tailwind depends on a runtime CDN, reducing repeatability.

## Verification evidence

- Default local allocation: USD 50,000 allocated across Orpheum, Sumfer and Pdm, claiming 18 downstream businesses and 7.52 expected protected equivalents. This calculation did not query BigQuery or run an ADK tool.
- Deliberate offline request reproduced the unlabeled canned graph-engine response described above.
- Carve-out and partial-grant cases were executed locally; percentages and amounts above are observed outputs, not inferred behavior.
- A real `/api/chat` function invocation to `cascade_analyst` succeeded against Cloud Run, returning `analyze_cascade` and Orpheum supply-disruption counts of seven baseline/seven filtered; it also returned customer-loss counts of 15 baseline/11 filtered. This establishes that the chat integration can reach a live agent, not that the queue, mock edges or memo are live.
- An unauthenticated HTTP request to the deployed ADK `/list-apps` returned 200 during this review. Earlier documentation describing the agent as private is stale relative to that observation; lack of authentication headers is not currently the observed integration blocker. The frontend has no identity-token support if the service is made private again.

## Recommended order

1. Remove false provenance and disguised fallback results.
2. Make live structured comparison results authoritative for allocation, counts and memo; expose shortlist and financial assumptions.
3. Isolate sessions, sanitize rendering, and add explicit failure handling.
4. Surface live paths/traversal, reviewer findings, neighborhood context and memo export.
5. Compute the outcome equity audit and sensitivity from actual allocation results.

Retain the queue and contextual chat layout. A coherent, traceable funding decision would strengthen Impact & insight (30%), Technical execution (30%) and Rigor & judgment (25%); more agents or static panels would not resolve the current evidence gaps.
