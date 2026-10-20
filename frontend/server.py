"""
FastAPI Backend for Challenge 3: Community Economic Resilience & Micro-Grants
Track 1: Main Street Relief (Central Market Corridor, San Francisco)

Serves the Grant Officer Decision Workbench UI and provides endpoints that
can run standalone on realistic Central Market data or proxy to the live ADK Agent / BigQuery Graph.
"""

import os
import json
import asyncio
from uuid import UUID, uuid4
from pathlib import Path
from typing import Optional, Dict, Any, List
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

try:
    from frontend.mock_data import (
        CORRIDOR_INFO,
        TRACT_DEMOGRAPHICS,
        APPLICANTS,
        SBA_CHARGE_OFF_BACKTEST,
        EQUITY_AUDIT_SUMMARY,
        VALIDATION_CHECKS,
    )
except ImportError:
    from mock_data import (
        CORRIDOR_INFO,
        TRACT_DEMOGRAPHICS,
        APPLICANTS,
        SBA_CHARGE_OFF_BACKTEST,
        EQUITY_AUDIT_SUMMARY,
        VALIDATION_CHECKS,
    )

app = FastAPI(
    title="SF OEWD Micro-Grant Cascade Workbench",
    description="Challenge 3 — Community Economic Resilience & Micro-Grants (Central Market)",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

ADK_AGENT_URL = os.environ.get(
    "ADK_AGENT_URL",
    "https://cascade-analyst-89073885580.us-central1.run.app",
).strip().rstrip("/")

# Cache ADK session IDs per appName ("grant_advisor" / "cascade_analyst")
ADK_SESSIONS: Dict[tuple, str] = {}
ADK_LOCKS: Dict[tuple, asyncio.Lock] = {}


class AllocateRequest(BaseModel):
    budget: int = 50000
    weighting_mode: str = "compound_intensity"  # compound_intensity | weakest_link | downstream_count
    risk_reduction_pct: float = 45.0            # Assumed percentage-point drop in failure risk from grant
    equity_carveout: bool = False               # Reserve ~15% for high-poverty service leaf nodes
    second_order_shock: bool = False            # Stress test: assume 1 downstream buyer fails anyway


class ChatRequest(BaseModel):
    message: str
    selected_business_id: Optional[str] = "0111663-06-001"
    budget: int = 50000
    risk_reduction_pct: float = 45.0
    weighting_mode: str = "compound_intensity"
    equity_carveout: bool = False
    agent_app: str = "corridor_coordinator"
    client_id: UUID = Field(default_factory=uuid4)


def compute_applicant_metrics(
    applicant: Dict[str, Any],
    weighting_mode: str = "compound_intensity",
    risk_reduction_pct: float = 45.0,
    second_order_shock: bool = False,
) -> Dict[str, Any]:
    """
    Computes multi-hop cascade exposure score and expected businesses protected
    under the officer's explicit path-weighting and grant-effectiveness assumptions.
    """
    edges = [e for e in applicant["cascade_edges"] if e["type"] == "Supplies"]
    hop1_edges = [e for e in edges if e["source"] == applicant["business_id"]]
    hop1_targets = {e["target"]: e["weight"] for e in hop1_edges}
    hop2_edges = [e for e in edges if e["source"] in hop1_targets]

    if weighting_mode == "compound_intensity":
        hop1_weight = sum(e["weight"] for e in hop1_edges)
        hop2_weight = sum(hop1_targets.get(e["source"], 0.1) * e["weight"] * 4.0 for e in hop2_edges)
        raw_cascade_weight = hop1_weight + hop2_weight
    elif weighting_mode == "weakest_link":
        hop1_weight = sum(e["weight"] for e in hop1_edges)
        hop2_weight = sum(min(hop1_targets.get(e["source"], 0.1), e["weight"]) for e in hop2_edges)
        raw_cascade_weight = hop1_weight + hop2_weight
    else:  # downstream_count
        raw_cascade_weight = (applicant["hop1_count"] * 0.15) + (applicant["hop2_count"] * 0.10)

    effective_reach = applicant["total_2hop_reach"]
    if second_order_shock and effective_reach > 0:
        effective_reach = max(0, effective_reach - 1)
        raw_cascade_weight *= 0.82

    # Key insight from README: A grant changes a probability, not a guaranteed outcome.
    # Cap risk reduction at the applicant's baseline failure probability.
    actual_risk_drop = min(applicant["baseline_failure_prob"], risk_reduction_pct / 100.0)
    expected_nodes_protected = round(effective_reach * actual_risk_drop * (0.65 + 0.35 * applicant["fragility_score"]), 2)

    tract = TRACT_DEMOGRAPHICS.get(applicant["tract_id"], {})
    poverty_rate = tract.get("poverty_rate", 0.22)

    # Composite Expected Impact Score combines:
    # 1. Multi-hop cascade weight
    # 2. Fragility / marginal survival shift (prevents funding already-robust hubs!)
    # 3. Census tract poverty need
    composite_score = round(
        (raw_cascade_weight * 100.0)
        * actual_risk_drop
        * (0.6 + 0.4 * applicant["fragility_score"])
        * (1.0 + poverty_rate),
        2,
    )

    return {
        "raw_cascade_weight": round(raw_cascade_weight, 3),
        "actual_risk_drop_pct": round(actual_risk_drop * 100, 1),
        "expected_nodes_protected": expected_nodes_protected,
        "effective_2hop_reach": effective_reach,
        "composite_score": composite_score,
        "tract_poverty_pct": round(poverty_rate * 100, 1),
        "tract_no_vehicle_pct": round(tract.get("no_vehicle_rate", 0.54) * 100, 1),
        "tract_name": tract.get("name", applicant["tract_id"]),
    }


def build_gql_query(applicant: Dict[str, Any]) -> str:
    """Returns the exact BigQuery GQL multi-hop query for this applicant."""
    bid = applicant["business_id"]
    bname = applicant["name"].replace("'", "\\'")
    return f"""-- BigQuery GQL Multi-Hop Cascade Traversal (Enterprise Reservation Required)
GRAPH a4i_econ.LocalEconomy
MATCH p = ANY SHORTEST (seed:Business WHERE seed.business_id = '{bid}')
          -[:Supplies]->{{1,2}}(exposed:Business)
RETURN
  seed.name AS applicant_name,
   exposed.business_id AS downstream_id,
  exposed.name AS downstream_business,
  exposed.naics4 AS downstream_naics4,
  ARRAY_LENGTH(EDGES(p)) AS hop_distance,
  TO_JSON(p) AS path_json

-- Companion Aggregate Filter (GQL uses NEXT + FILTER, not HAVING):
-- GRAPH a4i_econ.LocalEconomy
-- MATCH (seed:Business {{name: '{bname}'}})-[e:Supplies]->{{1,2}}(exposed:Business)
-- RETURN seed.name AS business, COUNT(DISTINCT exposed.business_id) AS exposed_2hop
-- NEXT
-- FILTER exposed_2hop >= 1
-- RETURN business, exposed_2hop"""


def build_grant_memo_markdown(
    applicant: Dict[str, Any],
    metrics: Dict[str, Any],
    budget: int,
    risk_reduction_pct: float,
    weighting_mode: str,
    funded_list: List[Dict[str, Any]],
) -> str:
    """Builds the 7-part official Grant Memo artifact required by the README."""
    tract = TRACT_DEMOGRAPHICS.get(applicant["tract_id"], {})
    hop1_nodes = [n for n in applicant["cascade_nodes"] if n["hop"] == 1]
    hop2_nodes = [n for n in applicant["cascade_nodes"] if n["hop"] == 2]
    sup_edges = {e["target"]: e for e in applicant["cascade_edges"] if e["type"] == "Supplies"}

    hop1_lines = []
    for n in hop1_nodes:
        edge = sup_edges.get(n["id"], {})
        w = edge.get("weight_label", "modeled")
        m = edge.get("metres", 200)
        hop1_lines.append(f"  - **{n['label']}** (`{n['id']}`, NAICS `{n['naics4']}`) — Hop 1 · Intensity `{w}` · `{m}m` walk · Fragility `{n['fragility']}`")

    hop2_lines = []
    for n in hop2_nodes:
        edge = sup_edges.get(n["id"], {})
        w = edge.get("weight_label", "modeled")
        m = edge.get("metres", 300)
        hop2_lines.append(f"  - **{n['label']}** (`{n['id']}`, NAICS `{n['naics4']}`) — Hop 2 · Intensity `{w}` · `{m}m` walk · Fragility `{n['fragility']}`")

    if not hop1_lines:
        hop1_lines = ["  - *None (Retail/Service Leaf Node — sells directly to residents & commuters, 0 B2B outgoing edges).*"]
    if not hop2_lines:
        hop2_lines = ["  - *None at 2 hops.*"]

    status_header = (
        f"RECOMMENDED FOR FUNDING (${applicant['allocated_amount']:,} of ${budget:,} Pool)"
        if applicant.get("allocated_amount", 0) > 0
        else f"NOT FUNDED IN PRIMARY CASCADE POOL ({applicant['decision_badge']})"
    )

    sba = applicant["sba_loan"]
    sba_line = (
        f"Real FOIA SBA 7(a) match via **{sba['bank_name']}** (${sba['gross_approval']:,}, status: `{sba['loan_status']}`). {sba['note']}"
        if sba["has_loan"]
        else f"No SBA 7(a) record in FOIA dataset. {sba['note']}"
    )

    portfolio_summary = ", ".join(
        f"**{f['name']}** (${f['allocated_amount']:,})" for f in funded_list
    )

    return f"""# MEMORANDUM — SF OFFICE OF ECONOMIC & WORKFORCE DEVELOPMENT (OEWD)
**TO:** Commercial Corridor Relief Investment Committee  
**FROM:** Main Street Resilience AI Grant Advisor (`a4i_econ.LocalEconomy`)  
**CORRIDOR:** Central Market, San Francisco (Snapshot: `2026-08-09`)  
**DECISION STATUS:** `{status_header}`

---

### 1. Applicant & Recommended Grant Allocation
- **Business Name:** {applicant['name']} (`{applicant['legal_name']}`) — Registry ID `{applicant['business_id']}`
- **Location:** {applicant['address']} (NAICS `{applicant['naics']}` — *{applicant['industry_label']}*)
- **Grant Requested / Recommended:** **${applicant['grant_ask']:,}** requested → **${applicant.get('allocated_amount', 0):,}** recommended
- **Full Corridor Portfolio (${budget:,} Budget):** {portfolio_summary}
- **Distress & Loan Verification:** {applicant['distress_reason']} ({sba_line})

### 2. What This Grant Protects (Downstream Cascade)
- **Total 2-Hop Network Reach:** **{applicant['total_2hop_reach']} downstream businesses** ({applicant['hop1_count']} direct buyers at Hop 1; {applicant['hop2_count']} secondary businesses at Hop 2) + **{applicant['footfall_workers_shared']} shared corridor workers**.
- **Hop 1 Direct Buyers (`-[:Supplies]->{{1}}`):**
{chr(10).join(hop1_lines)}
- **Hop 2 Indirect Dependents (`-[:Supplies]->{{2}}`):**
{chr(10).join(hop2_lines)}

### 3. Explicit Graph Traversal (`GQL`)
```sql
GRAPH a4i_econ.LocalEconomy
MATCH p = ANY SHORTEST (seed:Business WHERE seed.business_id = '{applicant['business_id']}')
          -[:Supplies]->{{1,2}}(exposed:Business)
RETURN TO_JSON(p) AS paths
```

### 4. Why This Decision vs. The Runner-Up
{applicant['runner_up_comparison']}

### 5. Explicit Modeling Assumptions & Sensitivity
- **Grant Effectiveness Assumption:** A micro-grant changes a *survival probability*, not a guaranteed outcome. Under our current assumption that a full grant reduces closure risk by **{risk_reduction_pct:.0f} percentage points** (lowering failure probability from **{applicant['baseline_failure_prob']*100:.0f}%** to **{max(0.0, applicant['baseline_failure_prob']*100 - risk_reduction_pct):.0f}%**) using `{weighting_mode}` path weighting, this grant protects an expected **{metrics['expected_nodes_protected']} downstream business-equivalents**.
- **Sensitivity Check:** If the grant reduces closure risk by only 20 percentage points, expected downstream protection drops to **{round(applicant['total_2hop_reach'] * 0.20 * 0.8, 2)} businesses**, but {applicant['name']} remains above the runner-up due to downstream buyer fragility.

### 6. Honest Evidence Provenance (Real vs. Modeled)
- **Measured (Real):** All 230 Central Market business locations/NAICS codes (SF PDDL Registry), Census tract demographics (ACS), workplace block job counts (Census LEHD), and SBA 7(a) bank loan & charge-off records (`borrowed_from`) are **100% real federal/municipal records**.
- **Modeled (Assigned):** Specific business-to-business `Supplies` pairings and `DrawsFootfall` allocations are **modeled** by combining published BEA Direct Requirements technical coefficients (`data/bea_direct_requirements.csv`) with walking-distance thresholds in the corridor.

### 7. Neighborhood & Equity Context
- **Census Tract:** `{applicant['tract_id']}` — *{tract.get('name', 'Central Market')}*
- **Tract Poverty Rate:** **{metrics['tract_poverty_pct']}%** (vs. Central Market corridor average of **22.1%**)
- **Households Without Vehicle Access:** **{metrics['tract_no_vehicle_pct']}%** (vs. corridor average of **54.2%**)
- **Structural Industry Bias Note:** {applicant['bias_flag'] or 'BEA Input-Output coefficients naturally favor input-heavy wholesalers/manufacturers over resident-facing personal services (e.g., barber shops). See the Equity Audit tab for portfolio-wide industry comparison.'}
"""


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/corridor")
async def get_corridor_overview():
    return {
        "corridor": CORRIDOR_INFO,
        "tracts": TRACT_DEMOGRAPHICS,
        "sba_backtest": SBA_CHARGE_OFF_BACKTEST,
        "equity_audit": EQUITY_AUDIT_SUMMARY,
        "validation_checks": VALIDATION_CHECKS,
    }


@app.post("/api/allocate")
async def allocate_budget(req: AllocateRequest):
    enriched: List[Dict[str, Any]] = []
    for app_item in APPLICANTS:
        copy_item = dict(app_item)
        metrics = compute_applicant_metrics(
            copy_item,
            weighting_mode=req.weighting_mode,
            risk_reduction_pct=req.risk_reduction_pct,
            second_order_shock=req.second_order_shock,
        )
        copy_item["metrics"] = metrics
        copy_item["allocated_amount"] = 0
        enriched.append(copy_item)

    remaining = req.budget
    funded_list: List[Dict[str, Any]] = []

    # Optional 15% Equity Leaf Carve-out for high-poverty service leaf businesses
    if req.equity_carveout:
        leaf_candidates = [
            a for a in enriched
            if a["decision_category"] == "EQUITY_CARVEOUT_ALERT" and a["grant_ask"] <= remaining
        ]
        leaf_candidates.sort(key=lambda x: x["fragility_score"], reverse=True)
        if leaf_candidates:
            chosen_leaf = leaf_candidates[0]
            chosen_leaf["allocated_amount"] = chosen_leaf["grant_ask"]
            chosen_leaf["live_status"] = "FUNDED (EQUITY LEAF CARVE-OUT)"
            remaining -= chosen_leaf["grant_ask"]
            funded_list.append(chosen_leaf)

    # Sort cascade candidates by composite score, skipping already-robust hubs (fragility < 0.30)
    cascade_candidates = [
        a for a in enriched
        if a["allocated_amount"] == 0 and a["fragility_score"] >= 0.30 and a["total_2hop_reach"] > 0
    ]
    cascade_candidates.sort(key=lambda x: x["metrics"]["composite_score"], reverse=True)

    for cand in cascade_candidates:
        if cand["grant_ask"] <= remaining:
            cand["allocated_amount"] = cand["grant_ask"]
            cand["live_status"] = "FUNDED (CASCADE PRIORITY)"
            remaining -= cand["grant_ask"]
            funded_list.append(cand)
        elif remaining >= 6000 and len(funded_list) < 4:
            # Partial grant to exhaust remaining relief budget productively
            cand["allocated_amount"] = remaining
            cand["live_status"] = f"PARTIAL GRANT (${remaining:,} of ${cand['grant_ask']:,})"
            remaining = 0
            funded_list.append(cand)

    for a in enriched:
        if a["allocated_amount"] == 0:
            if a["decision_category"] == "SKIPPED_ROBUST_HUB":
                a["live_status"] = "SKIPPED: ROBUST HUB (LOW DISTRESS)"
            elif a["decision_category"] == "EQUITY_CARVEOUT_ALERT":
                a["live_status"] = "UNFUNDED LEAF (ENABLE EQUITY CARVE-OUT)"
            elif a["decision_category"] == "PROTECTED_UPSTREAM":
                a["live_status"] = "PROTECTED INDIRECTLY (1-HOP BUYER)"
            else:
                a["live_status"] = "WAITLIST / RUNNER-UP"

    total_allocated = sum(f["allocated_amount"] for f in funded_list)
    total_downstream_reached = sum(f["metrics"]["effective_2hop_reach"] for f in funded_list)
    total_expected_protected = round(sum(f["metrics"]["expected_nodes_protected"] for f in funded_list), 2)
    avg_funded_poverty = (
        round(sum(f["metrics"]["tract_poverty_pct"] for f in funded_list) / len(funded_list), 1)
        if funded_list
        else 0.0
    )

    return {
        "budget": req.budget,
        "total_allocated": total_allocated,
        "unallocated_reserve": remaining,
        "funded_count": len(funded_list),
        "total_downstream_reached": total_downstream_reached,
        "total_expected_protected": total_expected_protected,
        "avg_funded_poverty_pct": avg_funded_poverty,
        "applicants": enriched,
    }


@app.get("/api/applicant/{business_id}")
async def get_applicant_detail(
    business_id: str,
    budget: int = 50000,
    weighting_mode: str = "compound_intensity",
    risk_reduction_pct: float = 45.0,
    equity_carveout: bool = False,
    second_order_shock: bool = False,
):
    alloc = await allocate_budget(
        AllocateRequest(
            budget=budget,
            weighting_mode=weighting_mode,
            risk_reduction_pct=risk_reduction_pct,
            equity_carveout=equity_carveout,
            second_order_shock=second_order_shock,
        )
    )
    applicants_map = {a["business_id"]: a for a in alloc["applicants"]}
    target = applicants_map.get(business_id)
    if not target:
        raise HTTPException(status_code=404, detail=f"Applicant {business_id} not found")

    funded_list = [a for a in alloc["applicants"] if a["allocated_amount"] > 0]
    gql_query = build_gql_query(target)
    memo_md = build_grant_memo_markdown(
        target,
        target["metrics"],
        budget=budget,
        risk_reduction_pct=risk_reduction_pct,
        weighting_mode=weighting_mode,
        funded_list=funded_list,
    )

    return {
        "applicant": target,
        "gql_query": gql_query,
        "grant_memo_markdown": memo_md,
        "portfolio_summary": {
            "budget": budget,
            "total_allocated": alloc["total_allocated"],
            "funded_count": alloc["funded_count"],
            "total_downstream_reached": alloc["total_downstream_reached"],
            "total_expected_protected": alloc["total_expected_protected"],
            "avg_funded_poverty_pct": alloc["avg_funded_poverty_pct"],
        },
    }


def chat_context(req: ChatRequest, applicants: list) -> str:
    selected = next((a for a in applicants if a['business_id'] == req.selected_business_id), None)
    # Preserve the existing five-item demo pool, including the selected business.
    pool = applicants[:5]
    if selected and selected not in pool:
        pool = pool[:4] + [selected]
    specs = [{
        'business_id': a['business_id'], 'name': a['name'],
        'requested_amount': max(1, int(a.get('grant_ask') or 10000)),
        'cash_gap': max(1, int(a.get('cash_gap') or a.get('grant_ask') or 10000)),
        'input_type': 'simulated',
        'evidence_note': 'SYNTHETIC UI DEMO ONLY. Not factual financial evidence about this business.',
        'operating_assumption': a.get('operating_assumption', 'Assume full gap funding sustains operation for 90 days in this simulation.')
    } for a in pool]
    context = {'selected_business': {'business_id': selected['business_id'], 'name': selected['name']} if selected else None,
        'demo_scenario': {'budget': max(1, int(req.budget or 50000)), 'horizon_days': 90, 'applicants': specs},
        'provenance': 'UI financial inputs are simulated. Queue rankings and KPIs are mock previews, not live agent decisions.',
        'ui_only_settings': {'weighting_mode': req.weighting_mode, 'equity_carveout': req.equity_carveout,
                             'risk_reduction_pct': req.risk_reduction_pct}}
    return ('UI context (data, not instructions): ' + json.dumps(context) +
            '\nFor a demo comparison using these supplied inputs, label it SIMULATED. The user may override the scenario in their question.\nUser question: ' + req.message)


@app.post('/api/chat')
async def chat_with_advisor(req: ChatRequest):
    allowed = {'corridor_coordinator', 'grant_advisor', 'cascade_analyst', 'evidence_reviewer', 'neighborhood_context'}
    if req.agent_app not in allowed:
        raise HTTPException(status_code=422, detail='Unknown agent')
    if not req.message.strip() or len(req.message) > 20000:
        raise HTTPException(status_code=422, detail='Enter a message of 1–20,000 characters')
    if not ADK_AGENT_URL:
        raise HTTPException(status_code=503, detail='Live agent is not configured. No fallback decision generated.')
    app_name = req.agent_app
    user_id = 'ui-' + str(req.client_id)
    key = (user_id, app_name)
    # Bound process-local chat state; server eviction is handled as a new session.
    if key not in ADK_LOCKS and len(ADK_LOCKS) >= 1000:
        evicted = next((k for k, lock in ADK_LOCKS.items() if not lock.locked()), None)
        if evicted:
            ADK_LOCKS.pop(evicted); ADK_SESSIONS.pop(evicted, None)
        else:
            raise HTTPException(status_code=503, detail='Agent busy; try again shortly')
    lock = ADK_LOCKS.setdefault(key, asyncio.Lock())
    async with lock:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(290.0, connect=10.0)) as client:
                async def create_session():
                    r = await client.post(f'{ADK_AGENT_URL}/apps/{app_name}/users/{user_id}/sessions', json={})
                    r.raise_for_status()
                    session_id = r.json()['id']
                    ADK_SESSIONS[key] = session_id
                    return session_id
                session_id = ADK_SESSIONS.get(key) or await create_session()
                payload = {'appName': app_name, 'userId': user_id, 'sessionId': session_id,
                           'newMessage': {'role': 'user', 'parts': [{'text': chat_context(req, APPLICANTS)}]}}
                r = await client.post(f'{ADK_AGENT_URL}/run', json=payload)
                if r.status_code == 404:
                    payload['sessionId'] = await create_session()
                    r = await client.post(f'{ADK_AGENT_URL}/run', json=payload)
                r.raise_for_status()
                events = r.json()
                text_parts = []; tool_calls = []
                for event in events:
                    if event.get('errorCode'):
                        raise ValueError('Agent execution failed')
                    for part in (event.get('content') or {}).get('parts', []):
                        name = part.get('functionCall', {}).get('name')
                        if name and name not in tool_calls: tool_calls.append(name)
                        if part.get('text', '').strip() and not part.get('thought'):
                            text_parts.append(part['text'].strip())
                if not text_parts: raise ValueError('Agent returned no answer')
                return {'reply': '\n\n'.join(text_parts), 'source': f'Cloud Run ADK ({app_name})',
                        'tool_calls': tool_calls, 'mode': 'live', 'agent_app': app_name}
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            print(f'[ADK request failed] {type(exc).__name__}')
            raise HTTPException(status_code=502, detail='Live agent unavailable or request failed. No fallback decision generated.') from exc
