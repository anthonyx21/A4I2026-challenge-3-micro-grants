# Corridor grant agents

A Python ADK specialist that resolves real corridor businesses, calls Google's MCP Toolbox
over Streamable HTTP, traverses a BigQuery property graph, and summarizes modeled cascade
evidence. It runs alone and is also available as a specialist tool to Grant Advisor.

It supports two distinct mechanisms:

- `supply_disruption`: supplier → buyers; potential disruption when a supplier closes.
- `customer_loss`: buyer → suppliers; potential demand loss when a buyer closes.

Depth defaults to two. Sensitivity defaults to removing edges with intensity below 0.01.
The threshold applies inside the graph traversal, so qualifying alternate paths remain eligible.
One arbitrary shortest path is returned for each reachable business. This does not find the
strongest path, estimate closure probability, or calculate jobs saved. All supply links are modeled.

## Start in Cloud Shell

From this repository's `agent/` directory, use Python 3.11 or newer:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python setup.py
.venv/bin/python install_toolbox.py
bin/toolbox --config tools.yaml --address 127.0.0.1 --port 5000
```

`setup.py` validates business/edge keys and supply endpoints, then creates `CascadeEconomy`
metadata if absent. It preserves all existing tables and graphs. If an existing graph with this
name has incompatible properties, inspect it before replacing it. Runtime tools are fixed read-only
queries, restricted to the configured dataset. The Toolbox binary is pinned to v1.14.0 and checked
against Google's published SHA256.

In another terminal, from `agent/`:

```bash
.venv/bin/python smoke.py
.venv/bin/python run.py --verify-tools 'Analyze the supply-disruption cascade for Steel + Lacquer at two hops. Include sensitivity to weak modeled links.'
.venv/bin/adk web --host 0.0.0.0 --port 8080 .
```

Use Cloud Shell Web Preview on port 8080, select `cascade_analyst`, and enter a business name.
The ADK development UI supplies a chat interface; a custom graph UI is not part of this specialist.
Cloud Shell processes are temporary and this is not a Cloud Run deployment.

## Cloud Run

`Dockerfile` packages the agent and the verified Toolbox binary together. `start_service.py`
supervises both processes; Toolbox listens only on localhost. `service.py` serves the ADK
API/chat UI with a maximum of eight LLM calls per request. `/api/health` checks the MCP connection.
The `.env` file and local reports are excluded from Docker and Cloud Build uploads.

Deploy with `bash deploy.sh` after setting up the dedicated `cascade-analyst` service account.
Runtime access is BigQuery jobUser, dataset READER on `a4i_econ`, and Vertex AI user. The
Cloud Run service requires authentication, scales to zero, and is capped at three instances.

Open the authenticated app from Cloud Shell:

```bash
gcloud run services proxy cascade-analyst --project=qwiklabs-gcp-04-029c15637557 --region=us-central1 --port=8081
```

Then use Web Preview on port 8081 and open `/dev-ui/`. The proxy supplies the active Google
identity; a bare service URL does not present a Google sign-in page. Callers need Cloud Run
Invoker or an equivalent project role. No public invoker binding is configured.

Chat sessions use memory and can disappear when an instance restarts or traffic reaches a
different instance. This deployment is suitable for an initial demo; durable shared session
storage remains a future improvement.

Cloud Shell supplies ADC. On a local workstation, use `gcloud auth application-default login`
and choose the same project. The runtime identity needs BigQuery job creation and dataset read
access. Graph setup additionally needs graph creation privileges. Vertex AI access is needed for
Gemini calls. Model defaults to `gemini-2.5-flash`; change `AGENT_MODEL` to an available model
if the lab project has different access.

The notebook's Enterprise/Enterprise Plus QUERY reservation in `US` must be active for graph
queries. Setup does not create an additional reservation. If the reservation error appears, use
notebook section 1b and allow its assignment to propagate.

## Configuration

Copy `.env.example` to `.env`. Configure project, dataset, graph, corridor, BigQuery location,
Vertex location/model and Toolbox URL. Use a dedicated dataset for each corridor. Setup rejects
mixed-corridor data. Changing CORRIDOR alone does not load another corridor.

## Verification

```bash
.venv/bin/pip install pytest
.venv/bin/pytest -q
```

Tests cover unique-endpoint counts, repeated paths, cycles, reverse edge semantics, MCP errors,
and sensitivity that retains qualifying alternate paths. `smoke.py` verifies an actual MCP-backed
multi-hop cascade over the loaded Central Market data. `run.py --verify-tools` requires successful
search and analysis calls from the live model, not just a plausible text response.

Outputs contain seed identity, graph, direction/depth, direct/multi-hop counts, all exposed business
identities, up to eight named example paths, baseline and filtered results, sensitivity and limitations.
Missing seed, MCP failure or truncated results return explicit statuses. Names are never invented
to compensate for a failed query.

## Grant Advisor

Select `grant_advisor` in the same ADK chat UI. It resolves applicant identities, runs the custom
`compare_applicants` tool against live Cascade Analyst evidence, and writes a conditional grant memo.
The Cascade Analyst agent is also a callable ADK `AgentTool` for graph explanations and follow-ups.
The calculator consumes structured graph evidence directly rather than extracting numbers from prose.

Supply a USD budget, a horizon of 1–365 days, and two to six applicants. Each applicant needs:
`business_id`, `requested_amount`, `cash_gap`, `input_type` (`verified`, `applicant_reported`, or
`simulated`), `evidence_note`, and `operating_assumption`. Explain how full gap funding would sustain
operation over the horizon. These are supplied assumptions; the loaded dataset contains no
applicant cash gaps or validated grant effects. Provenance labels are not an independent audit.

The policy funds supplied cash gaps in full, within requests and budget; it assumes no benefit
from partial grants. It enumerates feasible portfolios, maximizes unique filtered reachable
businesses, excludes funded recipients from exposure, and counts overlapping exposure once.
Ties favor lower spending, then stable business IDs. It compares the unfiltered choice and the
runner-up. A graph failure blocks a recommendation. Zero filtered exposure yields no network
recommendation. Network exposure is a conditional policy criterion, not predicted impact;
cultural value, neighborhood equity, substitutability and causal effects require additional evidence.

For a clearly labeled synthetic demo, paste the contents of `grant_advisor/demo.json` into chat
and say: "Produce a grant memo using these explicitly simulated inputs. They are not financial
facts about the named businesses." This tests real graph data with invented financial assumptions.

Verify the deployed agent with an authenticated Google identity:

```bash
.venv/bin/python verify_grants.py https://cascade-analyst-89073885580.us-central1.run.app
```

The check requires successful live comparison/MCP evidence, budget-consistent allocation, and
simulation labeling. It saves the tool trace and memo under ignored `reports/`.

## Evidence Reviewer

Select `evidence_reviewer` for a review of a scenario and optional draft memo. Supply the same
financial inputs required by Grant Advisor; add `memo_text` for wording review. Its custom
`review_grant_scenario` recomputes the live comparison and checks money reconciliation,
recipient identities, full-gap amounts, deduplicated exposure, simulated provenance and
sensitivity. Draft text is screened conservatively for causal, probability and approval language.
Phrase hits require contextual inspection and may include negated statements. The agent also
reads the draft qualitatively; this is distinct from deterministic calculator checks.

Successful consistency checks return `review_required`, never grant approval. Invalid or
incomplete evidence returns `blocked`. Financial documents and supplied "verified" labels
have not been independently audited. Outstanding evidence includes actual financial gaps,
operating plans, observed commercial links/substitutes, and community access/value.

Every Grant Advisor comparison now includes an automatic `evidence_review`. The standalone
Reviewer additionally handles draft wording. Grant Advisor can call it as a specialist agent.

## Neighborhood Context

Select `neighborhood_context` and enter a business name or ID. `get_neighborhood_context`
resolves the ID through MCP, then queries modeled footfall links and employer blocks grouped
by workplace tract, plus all public demographic rows in the configured single-corridor dataset.
No new graph or source data is created. The existing supply graph remains the multi-hop component.

Worker allocation remains fractional and represents modeled nearby demand, not observed visits
or employment at a business. Linked-block jobs belong to workplace census blocks. Coordinates
are approximated to tract internal points, and workers were allocated equally among nearby
consumer businesses within 500 metres. Independent business allocations share workers and cannot
be added as unique people.

Demographics describe tract populations, not verified customers or a business location. Poverty
uses people with determined poverty status; no-vehicle and assistance rates use households.
The stored rates are fractions. Missing demographic matches and absent modeled footfall are
explicit. Median incomes are not averaged and corridor rates are not inferred from missing
denominators. Source vintage metadata is unavailable in the loaded tables. The agent produces
context and evidence questions, without a demographic ranking or changes to the grant objective.

Grant Advisor can call Neighborhood Context for community/worker questions while keeping its
findings separate from supply-chain exposure and allocation.

Verify both deployed specialists:

```bash
.venv/bin/python verify_specialists.py https://cascade-analyst-89073885580.us-central1.run.app
```

This runs real Gemini tool calls and read-only MCP queries, checks nonempty worker links and
tract context, and requires simulated-input, sensitivity, causal-language and approval-language
review findings. Traces are saved in ignored `reports/`.
