# `agent/` — Main Street Relief: Corridor Grant Agents

This directory contains the **Google Agent Development Kit (`google-adk`)** multi-agent implementation for **Challenge 3 — Community Economic Resilience & Micro-Grants (🏢 Main Street Relief Track)**, pre-configured for:

- **GCP Project**: `qwiklabs-gcp-04-029c15637557`
- **BigQuery Dataset**: `a4i_econ` (`qwiklabs-gcp-04-029c15637557.a4i_econ`, location `US`)
- **BigQuery Property Graph**: `a4i_econ.CascadeEconomy` (`qwiklabs-gcp-04-029c15637557.a4i_econ.CascadeEconomy`)
- **Corridor**: `Central Market`
- **Model**: `gemini-2.5-flash` (via Vertex AI)
- **Deployed Cloud Run Service URL**: [https://cascade-analyst-89073885580.us-central1.run.app](https://cascade-analyst-89073885580.us-central1.run.app)

For detailed operational instructions, Cloud Run proxy usage, and decision policy details, see [`RUNBOOK.md`](./RUNBOOK.md) and [`VERIFICATION.md`](./VERIFICATION.md).

---

## How to Use the App

**Live Service URL**: [https://cascade-analyst-89073885580.us-central1.run.app](https://cascade-analyst-89073885580.us-central1.run.app)

### 1. Open the Web UI (`/dev-ui/`)
Because the Cloud Run service requires Google IAM authentication (`--no-allow-unauthenticated`), open an authenticated tunnel from Cloud Shell or your local workstation:
```bash
gcloud run services proxy cascade-analyst \
  --project=qwiklabs-gcp-04-029c15637557 \
  --region=us-central1 \
  --port=8081
```
Then open **`http://localhost:8081/dev-ui/`** (or use Cloud Shell **Web Preview** on port `8081` and navigate to `/dev-ui/`).
*(If running locally via `adk web`, open `http://localhost:8080/dev-ui/`.)*

### 2. Using `cascade_analyst` (Graph Cascade Analysis)
1. In the top-left agent dropdown of the ADK UI, select **`cascade_analyst`**.
2. Ask to analyze a Central Market business for either **supply disruption** (supplier closure affecting downstream buyers) or **customer loss** (buyer closure affecting upstream suppliers):
   - **Supply disruption prompt:**
     > `Analyze the supply-disruption cascade for Steel + Lacquer at two hops. Include sensitivity to weak modeled links.`
   - **Customer loss prompt:**
     > `Analyze the customer-loss cascade for Impark 0314 at two hops with minimum intensity 0.01.`
3. The agent resolves the business via `search_businesses`, runs `analyze_cascade` against `a4i_econ.CascadeEconomy`, and returns:
   - Seed business name and ID (`1026779-04-151` for Steel + Lacquer)
   - Baseline vs. filtered (`min_intensity >= 0.01`) direct and 2-hop unique exposed business counts
   - Named example shortest paths with edge intensities
   - Modeled-data caveats and sensitivity comparison

### 3. Using `grant_advisor` (Portfolio Allocation & Grant Memo)
1. In the top-left agent dropdown, select **`grant_advisor`**.
2. **Quick Synthetic Demo**: Paste the following prompt (from [`grant_advisor/demo.json`](./grant_advisor/demo.json)) into the chat:
   ```text
   Produce a grant memo using these explicitly simulated inputs. They are not financial facts about the named businesses:
   {
     "budget": 5000,
     "horizon_days": 30,
     "direction": "supply_disruption",
     "min_intensity": 0.01,
     "applicants": [
       {
         "business_id": "1026779-04-151",
         "requested_amount": 5000,
         "cash_gap": 5000,
         "input_type": "simulated",
         "evidence_note": "Synthetic demo only. No actual financial distress or request is known for Steel + Lacquer.",
         "operating_assumption": "For this simulation, assume full gap funding sustains operation for 30 days; no benefit from partial funding."
       },
       {
         "business_id": "1056704-02-161",
         "requested_amount": 5000,
         "cash_gap": 5000,
         "input_type": "simulated",
         "evidence_note": "Synthetic demo only. No actual financial distress or request is known for Impark 0314.",
         "operating_assumption": "For this simulation, assume full gap funding sustains operation for 30 days; no benefit from partial funding."
       }
     ]
   }
   ```
3. **Custom Applicant Evaluation**: Provide:
   - `budget`: Total grant fund in USD
   - `horizon_days`: Operating horizon (`1–365` days)
   - `2` to `6` applicants, each with `business_id` (or business name to resolve first), `requested_amount`, `cash_gap`, `input_type` (`verified`, `applicant_reported`, or `simulated`), `evidence_note`, and `operating_assumption`.
4. `grant_advisor` calls `compare_applicants` (which runs live `analyze_cascade` queries and automatic `evidence_review` checks for each portfolio) and outputs an auditable **Grant Memo**. It can also invoke `cascade_analyst`, `evidence_reviewer`, and `neighborhood_context` as specialist `AgentTool`s.

### 4. Using `evidence_reviewer` & `neighborhood_context`
- **`evidence_reviewer`**: Select `evidence_reviewer` in `/dev-ui/` and provide the applicant scenario plus optional `memo_text`. It runs `review_grant_scenario` to recompute live graph comparisons, verify money reconciliation, and screen draft wording for unsupported causal, probability, or approval language.
- **`neighborhood_context`**: Select `neighborhood_context` in `/dev-ui/` and enter a business name or ID (e.g., `Blick Art Materials LLC` / `1080659-07-161`). It runs `get_neighborhood_context` to summarize modeled worker-footfall allocations, linked workplace census blocks, and per-tract public demographic context with explicit denominator and modeled-data caveats.

### 5. Calling the Deployed App via CLI / API
You can also invoke and verify the live Cloud Run service directly from the terminal using your authenticated `gcloud` identity:
```bash
# Check service and MCP health (lists all 4 agents)
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  https://cascade-analyst-89073885580.us-central1.run.app/api/health

# Run automated live verification against the deployed service
.venv/bin/python verify_deployment.py https://cascade-analyst-89073885580.us-central1.run.app
.venv/bin/python verify_grants.py https://cascade-analyst-89073885580.us-central1.run.app
.venv/bin/python verify_specialists.py https://cascade-analyst-89073885580.us-central1.run.app
```

---

## Implemented Agents & Architecture

### 1. Cascade Analyst ([`cascade_analyst/`](./cascade_analyst/))
- [`cascade_analyst/config.py`](./cascade_analyst/config.py): Central environment and identifier validation (`PROJECT`, `DATASET`, `GRAPH`, `LOCATION`, `CORRIDOR`, `TOOLBOX_URL`, `MODEL`).
- [`cascade_analyst/queries.py`](./cascade_analyst/queries.py): Parameterized `CREATE PROPERTY GRAPH IF NOT EXISTS a4i_econ.CascadeEconomy` DDL, `SEARCH_SQL`, and `cascade_sql(depth, direction)` GQL queries.
- [`cascade_analyst/evidence.py`](./cascade_analyst/evidence.py): Deterministic normalization of BigQuery `TO_JSON(p)` graph paths, cycle detection, unique-endpoint summarization, and baseline-vs-filtered sensitivity comparison.
- [`cascade_analyst/tools.py`](./cascade_analyst/tools.py): ADK function tools consuming MCP Toolbox over Streamable HTTP:
  1. `search_businesses(query)`
  2. `analyze_cascade(business_id, direction="supply_disruption", depth=2, min_intensity=0.01)`
- [`cascade_analyst/agent.py`](./cascade_analyst/agent.py): Exports `root_agent` (`cascade_analyst`).

### 2. Grant Advisor ([`grant_advisor/`](./grant_advisor/))
- [`grant_advisor/decision.py`](./grant_advisor/decision.py): Exact-cent input validation (`validate`) and deterministic full-gap portfolio optimization (`allocate`).
- [`grant_advisor/tools.py`](./grant_advisor/tools.py): `compare_applicants` tool combining live `analyze_cascade` evidence, portfolio allocation, and automatic deterministic `evidence_review`.
- [`grant_advisor/agent.py`](./grant_advisor/agent.py): Exports `root_agent` (`grant_advisor`) equipped with `search_businesses`, `compare_applicants`, and `AgentTool` wrappers for `cascade_analyst`, `evidence_reviewer`, and `neighborhood_context`.
- [`grant_advisor/demo.json`](./grant_advisor/demo.json): Reproducible synthetic 2-applicant scenario (`Steel + Lacquer` vs. `Impark 0314`, $5,000 budget, 30-day horizon).

### 3. Evidence Reviewer ([`evidence_reviewer/`](./evidence_reviewer/))
- [`evidence_reviewer/review.py`](./evidence_reviewer/review.py) & [`evidence_reviewer/tools.py`](./evidence_reviewer/tools.py): `review_grant_scenario` recomputes live graph evidence, reconciles budgets/grants, and screens draft memo wording for unsupported causal or approval claims.
- [`evidence_reviewer/agent.py`](./evidence_reviewer/agent.py): Exports `root_agent` (`evidence_reviewer`).

### 4. Neighborhood Context ([`neighborhood_context/`](./neighborhood_context/))
- [`neighborhood_context/queries.py`](./neighborhood_context/queries.py) & [`neighborhood_context/tools.py`](./neighborhood_context/tools.py): `get_neighborhood_context` queries modeled worker-footfall links (`draws_footfall`, `employers`) and tract-level demographics (`demographics`) through MCP Toolbox.
- [`neighborhood_context/agent.py`](./neighborhood_context/agent.py): Exports `root_agent` (`neighborhood_context`).

### Setup, Runtime, Deployment & Tests
- [`setup.py`](./setup.py): Validates `businesses` and `supplies` keys/endpoints in BigQuery, creates `a4i_econ.CascadeEconomy`, and renders `tools.yaml` for MCP Toolbox.
- [`install_toolbox.py`](./install_toolbox.py): Downloads Google's MCP Toolbox binary (`v1.14.0`) to `bin/toolbox` and verifies its SHA256 checksum.
- [`service.py`](./service.py) & [`start_service.py`](./start_service.py): Supervises `bin/toolbox` and FastAPI (`get_fast_api_app` + `/api/health`) in the container.
- [`Dockerfile`](./Dockerfile) & [`deploy.sh`](./deploy.sh): Packages and deploys the authenticated `cascade-analyst` Cloud Run service.
- [`tests/test_evidence.py`](./tests/test_evidence.py), [`tests/test_grants.py`](./tests/test_grants.py), & [`tests/test_review_context.py`](./tests/test_review_context.py): 34-test unit suite.

---

## Quick Start (Cloud Shell / Linux or macOS with ADC)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python setup.py
.venv/bin/python install_toolbox.py
bin/toolbox --config tools.yaml --address 127.0.0.1 --port 5000
```

In a second terminal from `agent/`:
```bash
.venv/bin/pip install pytest
.venv/bin/pytest -q
.venv/bin/python smoke.py
.venv/bin/python run.py --verify-tools 'Analyze the supply-disruption cascade for Steel + Lacquer at two hops. Include sensitivity to weak modeled links.'
.venv/bin/adk web --host 0.0.0.0 --port 8080 .
```
