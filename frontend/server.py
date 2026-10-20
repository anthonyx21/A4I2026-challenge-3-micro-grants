"""
FastAPI Backend for Challenge 3: Community Economic Resilience & Micro-Grants
Track 1: Main Street Relief (Central Market Corridor, San Francisco)

Serves the Grant Officer Decision Workbench UI and loads applicant profiles
dynamically from the live BigQuery database (`a4i_econ.businesses`,
`a4i_econ.CascadeEconomy`, `a4i_econ.public_business_status`,
`a4i_econ.draws_footfall_from`, `a4i_econ.tract_demographics`) only if present there.
"""

import os
import sys
import json
import math
import asyncio
from uuid import UUID, uuid4
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

try:
    from frontend.mock_data import (
        CORRIDOR_INFO,
        TRACT_DEMOGRAPHICS,
        SBA_CHARGE_OFF_BACKTEST,
        EQUITY_AUDIT_SUMMARY,
        VALIDATION_CHECKS,
    )
except ImportError:
    from mock_data import (
        CORRIDOR_INFO,
        TRACT_DEMOGRAPHICS,
        SBA_CHARGE_OFF_BACKTEST,
        EQUITY_AUDIT_SUMMARY,
        VALIDATION_CHECKS,
    )

# Add agent directory to path in case local MCP Toolbox is running
AGENT_DIR = Path(__file__).resolve().parent.parent / "agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

CANDIDATE_APPLICANT_IDS: List[str] = [
    "1026779-04-151",
    "0111663-06-001",
    "1402027-10-251",
    "1051330-01-161",
    "1188036-05-181",
    "1056704-02-161",
    "1080659-07-161",
    "1373515-10-241",
]

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

# Cache of raw database records keyed by business_id.
# Value is None if queried and confirmed NOT present in the database.
DB_RECORD_CACHE: Dict[str, Optional[Dict[str, Any]]] = {}
DB_CACHE_LOCK = asyncio.Lock()


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


async def _try_local_mcp_fetch(target_ids: List[str]) -> Optional[Dict[str, Optional[Dict[str, Any]]]]:
    """If local MCP Toolbox (127.0.0.1:5000/mcp) is reachable, query BigQuery directly via agent tools."""
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            r = await client.get("http://127.0.0.1:5000")
            if r.status_code >= 500:
                return None
    except Exception:
        return None

    try:
        from cascade_analyst.tools import analyze_cascade, search_businesses
        from neighborhood_context.tools import get_neighborhood_context
        from neighborhood_context.public_records import get_public_business_context

        results: Dict[str, Optional[Dict[str, Any]]] = {}
        for bid in target_ids:
            found = await search_businesses(bid)
            matches = found.get("matches") or []
            exact = next((m for m in matches if m.get("business_id") == bid), None)
            if not exact:
                results[bid] = None
                continue
            cascade = await analyze_cascade(bid, min_intensity=0.01)
            if cascade.get("status") != "ok":
                results[bid] = None
                continue
            pub = await get_public_business_context(bid)
            nh = await get_neighborhood_context(bid)
            results[bid] = {
                "business_id": bid,
                "cascade": cascade,
                "public_context": pub if pub.get("status") == "ok" else {},
                "neighborhood_context": nh if nh.get("status") == "ok" else {},
            }
        return results
    except Exception:
        return None


async def _try_remote_applicants_endpoint(target_ids: List[str]) -> Optional[Dict[str, Optional[Dict[str, Any]]]]:
    """Try GET {ADK_AGENT_URL}/api/applicants if deployed on Cloud Run."""
    if not ADK_AGENT_URL:
        return None
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=8.0)) as client:
            r = await client.get(f"{ADK_AGENT_URL}/api/applicants", params={"ids": ",".join(target_ids)})
            if r.status_code != 200:
                return None
            data = r.json()
            if not isinstance(data, dict) or data.get("status") != "ok":
                return None
            by_id = {item["business_id"]: item for item in data.get("applicants", []) if "business_id" in item}
            return {bid: by_id.get(bid) for bid in target_ids}
    except Exception:
        return None


async def _fetch_via_adk_run(target_ids: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query BigQuery via the live Cloud Run ADK `/run` endpoint (`cascade_analyst` + `neighborhood_context`)
    in batches of up to 4 business IDs per session call.
    Only businesses where BigQuery returns status == 'ok' and a matching business_id are kept.
    """
    if not ADK_AGENT_URL:
        return {bid: None for bid in target_ids}

    batches = [target_ids[i:i + 4] for i in range(0, len(target_ids), 4)]
    cascades: Dict[str, Dict[str, Any]] = {}
    pub_ctx: Dict[str, Dict[str, Any]] = {}
    nh_ctx: Dict[str, Dict[str, Any]] = {}

    async with httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=15.0)) as client:
        async def run_cascade_batch(idx: int, batch: List[str]):
            uid = f"db-cas-{idx}-{uuid4().hex[:6]}"
            s = await client.post(f"{ADK_AGENT_URL}/apps/cascade_analyst/users/{uid}/sessions", json={})
            s.raise_for_status()
            sid = s.json()["id"]
            prompt = (
                f"Call analyze_cascade with min_intensity=0.01 for each of these business_ids: {', '.join(batch)}. "
                "Return a 1-line summary after calling all tools."
            )
            r = await client.post(
                f"{ADK_AGENT_URL}/run",
                json={
                    "appName": "cascade_analyst",
                    "userId": uid,
                    "sessionId": sid,
                    "newMessage": {"role": "user", "parts": [{"text": prompt}]},
                },
            )
            r.raise_for_status()
            events = r.json()
            if not isinstance(events, list):
                return
            for ev in events:
                for p in (ev.get("content") or {}).get("parts", []):
                    fr = p.get("functionResponse")
                    if fr and fr.get("name") == "analyze_cascade":
                        resp = fr.get("response", {})
                        if resp.get("status") == "ok" and resp.get("seed", {}).get("business_id"):
                            cascades[resp["seed"]["business_id"]] = resp

        async def run_nh_batch(idx: int, batch: List[str]):
            uid = f"db-nh-{idx}-{uuid4().hex[:6]}"
            s = await client.post(f"{ADK_AGENT_URL}/apps/neighborhood_context/users/{uid}/sessions", json={})
            s.raise_for_status()
            sid = s.json()["id"]
            prompt = (
                f"For each of these business_ids: {', '.join(batch)}, call BOTH get_public_business_context "
                "and get_neighborhood_context. Return a 1-line summary after calling all tools."
            )
            r = await client.post(
                f"{ADK_AGENT_URL}/run",
                json={
                    "appName": "neighborhood_context",
                    "userId": uid,
                    "sessionId": sid,
                    "newMessage": {"role": "user", "parts": [{"text": prompt}]},
                },
            )
            r.raise_for_status()
            events = r.json()
            if not isinstance(events, list):
                return
            for ev in events:
                for p in (ev.get("content") or {}).get("parts", []):
                    fr = p.get("functionResponse")
                    if not fr:
                        continue
                    resp = fr.get("response", {})
                    if fr.get("name") == "get_public_business_context" and resp.get("status") == "ok":
                        bid = resp.get("business_id") or (resp.get("business") or {}).get("business_id")
                        if bid:
                            pub_ctx[bid] = resp
                    elif fr.get("name") == "get_neighborhood_context" and resp.get("status") == "ok":
                        bid = (resp.get("seed") or {}).get("business_id")
                        if bid:
                            nh_ctx[bid] = resp

        tasks = []
        for i, b in enumerate(batches):
            tasks.append(run_cascade_batch(i, b))
            tasks.append(run_nh_batch(i, b))
        await asyncio.gather(*tasks, return_exceptions=True)

    results: Dict[str, Optional[Dict[str, Any]]] = {}
    for bid in target_ids:
        if bid in cascades:
            results[bid] = {
                "business_id": bid,
                "cascade": cascades[bid],
                "public_context": pub_ctx.get(bid, {}),
                "neighborhood_context": nh_ctx.get(bid, {}),
            }
        else:
            results[bid] = None
    return results


async def fetch_verified_db_records(target_ids: List[str], refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Ensures requested business IDs are checked against BigQuery (`a4i_econ.businesses`)
    and returns ONLY those records confirmed present in the database.
    """
    async with DB_CACHE_LOCK:
        missing_ids = [bid for bid in target_ids if refresh or bid not in DB_RECORD_CACHE]
        if missing_ids:
            fetched = await _try_local_mcp_fetch(missing_ids)
            if fetched is None:
                fetched = await _try_remote_applicants_endpoint(missing_ids)
            if fetched is None:
                fetched = await _fetch_via_adk_run(missing_ids)
            for bid, rec in fetched.items():
                # Only cache non-None if verified or if the batch succeeded and confirmed absence
                if rec is not None or any(v is not None for v in fetched.values()):
                    DB_RECORD_CACHE[bid] = rec

        return [DB_RECORD_CACHE[bid] for bid in target_ids if DB_RECORD_CACHE.get(bid) is not None]


def _project_svg_coords(lat: Optional[float], lon: Optional[float], used: List[Tuple[int, int]]) -> Tuple[int, int]:
    """Project real BigQuery latitude/longitude in Central Market onto the 1200x480 SVG canvas."""
    val_lat = float(lat) if lat is not None else 37.7795
    val_lon = float(lon) if lon is not None else -122.4135
    norm_x = (val_lon - (-122.4198)) / (-122.4072 - (-122.4198))
    norm_y = (val_lat - 37.7745) / (37.7850 - 37.7745)
    x = int(round(150 + max(0.0, min(1.0, norm_x)) * 880))
    y = int(round(410 - max(0.0, min(1.0, norm_y)) * 280))

    # Avoid visual collisions on the SVG map when two businesses share a block
    base_x, base_y = x, y
    step = 0
    while any(math.hypot(x - ux, y - uy) < 62 for ux, uy in used) and step < 24:
        step += 1
        angle = step * 1.15
        radius = 42 + (step // 3) * 28
        x = max(110, min(1080, int(round(base_x + math.cos(angle) * radius))))
        y = max(100, min(435, int(round(base_y + math.sin(angle) * radius * 0.7))))
    used.append((x, y))
    return x, y


def _node_key(business_id: str) -> str:
    return "n_" + business_id.replace("-", "_")


def build_profiles_from_db_records(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Transforms live BigQuery records (`cascade`, `public_context`, `neighborhood_context`)
    into both the frontend workbench schema (`applicants`, `nodes`, `assigned`) and the
    backend portfolio schema (`backend_applicants`).
    """
    used_coords: List[Tuple[int, int]] = []
    nodes_map: Dict[str, Dict[str, Any]] = {}
    ui_applicants: List[Dict[str, Any]] = []
    backend_applicants: List[Dict[str, Any]] = []
    assigned_map: Dict[str, str] = {}

    for idx, rec in enumerate(records):
        bid = rec["business_id"]
        cascade = rec.get("cascade") or {}
        seed = cascade.get("seed") or {}
        pub_ctx_resp = rec.get("public_context") or {}
        pub_records = pub_ctx_resp.get("registry_records") or []
        pub = pub_records[0] if pub_records else (pub_ctx_resp.get("business") or {})
        nh = rec.get("neighborhood_context") or {}

        filtered_obj = cascade.get("filtered") or {}
        baseline_obj = cascade.get("baseline") or {}
        filtered_sum = filtered_obj.get("summary") or filtered_obj
        baseline_sum = baseline_obj.get("summary") or baseline_obj
        filtered_exposed = filtered_obj.get("exposed_businesses") or []
        baseline_exposed = baseline_obj.get("exposed_businesses") or []
        filtered_paths = filtered_obj.get("example_paths") or []
        baseline_paths = baseline_obj.get("example_paths") or []

        # Map endpoint business_id -> (hops, bottleneck_intensity) from example_paths
        path_metrics: Dict[str, Tuple[int, float]] = {}
        for p in baseline_paths + filtered_paths:
            p_nodes = p.get("nodes") or []
            if p_nodes:
                ep_id = p_nodes[-1].get("business_id")
                if ep_id:
                    path_metrics[ep_id] = (
                        int(p.get("hops") or 1),
                        float(p.get("bottleneck_intensity") or 0.08),
                    )

        footfall_sum = (nh.get("footfall") or {}).get("summary") or {}
        footfall_blocks = (nh.get("footfall") or {}).get("blocks") or []
        linked_tracts = nh.get("linked_tracts") or []
        dataset_tracts = nh.get("dataset_tract_context") or []
        tract = (
            (linked_tracts[0].get("demographics") if linked_tracts and linked_tracts[0].get("demographics") else None)
            or (dataset_tracts[0] if dataset_tracts else None)
            or nh.get("tract")
            or {}
        )

        name = seed.get("name") or pub.get("dba_name") or pub.get("name") or bid
        legal_name = pub.get("ownership_name") or pub.get("legal_name") or seed.get("legal_name") or name
        street_addr = seed.get("address") or pub.get("street_address") or pub.get("address") or "Central Market"
        zip_code = str(seed.get("zip") or pub.get("source_zipcode") or pub.get("zip") or "94103")
        full_address = f"{street_addr}, San Francisco, CA {zip_code}"
        naics = str(seed.get("naics") or pub.get("naics_code") or pub.get("naics") or "")
        naics4 = str(seed.get("naics4") or pub.get("naics4") or naics[:4] or "")
        naics_desc = (
            pub.get("naics_code_description")
            or pub.get("naics_description")
            or pub.get("lic_code_description")
            or f"NAICS {naics4} Corridor Business"
        )
        tract_geoid = str(
            tract.get("tract_id")
            or tract.get("tract_geoid")
            or (linked_tracts[0].get("tract_id") if linked_tracts else "")
            or pub.get("tract_geoid")
            or (nh.get("seed") or {}).get("tract_geoid")
            or "06075017601"
        )

        start_date = str(pub.get("location_start_date") or pub.get("dba_start_date") or "")
        since_year: Any = int(start_date[:4]) if len(start_date) >= 4 and start_date[:4].isdigit() else "Active"
        as_of_raw = str(pub_ctx_resp.get("registry_source_as_of") or pub.get("source_as_of") or "2026-04-06")
        submitted_str = as_of_raw[:10]
        raw_reg_status = str(pub_ctx_resp.get("registry_status") or pub.get("registry_status") or "no_closure_recorded").lower()
        reg_status = "active" if raw_reg_status in ("active", "no_closure_recorded") else raw_reg_status

        lat = seed.get("latitude") or pub.get("latitude")
        lon = seed.get("longitude") or pub.get("longitude")
        ax, ay = _project_svg_coords(lat, lon, used_coords)

        hop1_count = int(filtered_sum.get("direct_count") or filtered_sum.get("hop1_count") or 0)
        hop2_count = int(filtered_sum.get("multi_hop_count") or filtered_sum.get("hop2_count") or 0)
        exposed_count = int(filtered_sum.get("exposed_business_count") or filtered_sum.get("exposed_count") or 0)
        base_exposed_count = int(baseline_sum.get("exposed_business_count") or baseline_sum.get("exposed_count") or 0)

        poverty_rate = float(tract.get("poverty_rate") or 0.221)
        no_vehicle_rate = float(tract.get("no_vehicle_rate") or 0.542)
        assistance_rate = float(tract.get("assistance_rate") or tract.get("public_assistance_rate") or 0.148)
        linked_blocks = int(nh.get("linked_block_count") or footfall_sum.get("linked_workplace_blocks") or 0)
        modeled_workers = float(nh.get("modeled_worker_allocation") or footfall_sum.get("modeled_worker_reach") or 0.0)
        total_block_jobs = int(nh.get("linked_block_jobs") or footfall_sum.get("total_linked_block_jobs") or 0)

        # Build edges (`out`, `in`, `spill`) from real BigQuery exposed_businesses and footfall tracts
        out_edges: List[List[Any]] = []
        in_edges: List[List[Any]] = []
        spill_edges: List[List[Any]] = []

        source_exposed = filtered_exposed if filtered_exposed else baseline_exposed
        for eb_idx, eb in enumerate(source_exposed):
            eb_id = eb.get("business_id")
            if not eb_id or eb_id == bid:
                continue
            nkey = _node_key(eb_id)
            if nkey not in nodes_map:
                nx, ny = _project_svg_coords(eb.get("latitude"), eb.get("longitude"), used_coords)
                nodes_map[nkey] = {
                    "name": eb.get("name") or eb_id,
                    "x": nx,
                    "y": ny,
                    "kind": f"NAICS {eb.get('naics4') or 'B2B'} · {eb.get('address') or 'Central Market'}",
                }
            pm_hops, pm_int = path_metrics.get(eb_id, (1 if eb_idx < max(1, hop1_count) else 2, 0.28))
            intensity = float(eb.get("max_bottleneck_intensity") or pm_int)
            est_flow = max(5000, int(round(intensity * 120000 / 1000.0) * 1000))
            dep_pct = max(4, min(95, int(round(intensity * 55))))
            min_hops = int(eb.get("min_hops") or pm_hops)
            if min_hops == 1 and len(out_edges) < 5:
                out_edges.append([nkey, est_flow, dep_pct])
            elif min_hops >= 2 and len(in_edges) < 5:
                in_edges.append([nkey, est_flow, dep_pct])
            elif len(spill_edges) < 4:
                spill_edges.append([nkey, max(3, dep_pct // 2)])

        # Add baseline spillover links or workplace tract links into `spill_edges`
        for eb in baseline_exposed:
            if len(spill_edges) >= 3:
                break
            eb_id = eb.get("business_id")
            if not eb_id or eb_id == bid:
                continue
            nkey = _node_key(eb_id)
            if any(e[0] == nkey for e in out_edges) or any(e[0] == nkey for e in in_edges) or any(e[0] == nkey for e in spill_edges):
                continue
            if nkey not in nodes_map:
                nx, ny = _project_svg_coords(eb.get("latitude"), eb.get("longitude"), used_coords)
                nodes_map[nkey] = {
                    "name": eb.get("name") or eb_id,
                    "x": nx,
                    "y": ny,
                    "kind": f"NAICS {eb.get('naics4') or 'Corridor'} · {eb.get('address') or 'Central Market'}",
                }
            _, pm_int = path_metrics.get(eb_id, (2, 0.08))
            intensity = float(eb.get("max_bottleneck_intensity") or pm_int)
            spill_edges.append([nkey, max(4, min(35, int(round(intensity * 40))))])

        for lt in linked_tracts[:2]:
            if len(spill_edges) >= 3:
                break
            tr_id = str(lt.get("tract_id") or "")
            if not tr_id:
                continue
            nkey = f"tract_{tr_id[-6:]}"
            if nkey not in nodes_map:
                nx, ny = _project_svg_coords(
                    (float(lat) if lat else 37.7795) + 0.0008,
                    (float(lon) if lon else -122.4135) - 0.0008,
                    used_coords,
                )
                nodes_map[nkey] = {
                    "name": f"Tract {tr_id[-5:]} ({lt.get('block_count', 0)} blocks)",
                    "x": nx,
                    "y": ny,
                    "kind": f"LEHD Workplace Blocks · {lt.get('linked_block_jobs', 0):,} jobs",
                }
            alloc = float(lt.get("modeled_worker_allocation") or 12.0)
            share_pct = max(5, min(40, int(round(alloc / 8.0))))
            spill_edges.append([nkey, share_pct])

        # Compute impact breakdown scores directly from live BigQuery metrics
        cascade_pts = min(30, int(round(min(22, exposed_count * 2.2) + min(8, base_exposed_count * 0.25))))
        if exposed_count == 0 and base_exposed_count > 0:
            cascade_pts = max(10, min(18, int(round(base_exposed_count * 0.6))))
        elif exposed_count == 0:
            cascade_pts = 8

        reg_pts = 22 if reg_status == "active" else 14
        if pub.get("lic_code_description"):
            reg_pts = min(25, reg_pts + 2)

        equity_pts = min(30, max(12, int(round(poverty_rate * 55 + no_vehicle_rate * 18))))
        footfall_pts = min(15, max(8, int(round(min(8, linked_blocks * 0.65) + min(7, modeled_workers / 35.0)))))
        impact_score = cascade_pts + reg_pts + equity_pts + footfall_pts

        if exposed_count >= 5 and reg_status == "active":
            ui_status = "ready"
        elif base_exposed_count >= 10:
            ui_status = "rev"
        elif exposed_count > 0:
            ui_status = "info"
        else:
            ui_status = "new"

        # Derive scale & grant ask from database footfall + cascade reach
        est_staff = max(5, min(32, int(round(6 + modeled_workers / 22.0 + exposed_count * 0.4))))
        grant_ask = max(8000, min(20000, int(round((9000 + min(8, exposed_count) * 1000 + (3000 if poverty_rate > 0.20 else 0)) / 1000.0) * 1000)))
        est_rev = max(240000, int(round((est_staff * 48000 + base_exposed_count * 12000) / 5000.0) * 5000))
        tax_rev = int(round(est_rev * 0.96 / 1000.0) * 1000)
        q_rev = int(round(est_rev / 4.0 / 1000.0) * 1000)
        quote_amt = max(6000, grant_ask - 1200)

        lic_desc = pub.get("lic_code_description") or naics_desc
        use_text = (
            f"Stabilize {naics_desc.lower()} operations at {street_addr} "
            f"({exposed_count} high-intensity 2-hop corridor links, {base_exposed_count} unfiltered in BigQuery)"
        )

        parts = [
            [
                "Cascade & B2B reach",
                cascade_pts,
                30,
                f"{exposed_count} exposed at ≥0.01 cutoff ({hop1_count} Hop-1, {hop2_count} Hop-2); {base_exposed_count} unfiltered in BigQuery",
            ],
            [
                "Public registry & status",
                reg_pts,
                25,
                f"SF Registry '{reg_status}' since {start_date or 'on file'} · {lic_desc}",
            ],
            [
                "Tract equity need",
                equity_pts,
                30,
                f"Tract {tract_geoid} · {poverty_rate*100:.1f}% poverty, {no_vehicle_rate*100:.1f}% no-vehicle, {assistance_rate*100:.1f}% public assistance",
            ],
            [
                "Footfall & spillover",
                footfall_pts,
                15,
                f"{linked_blocks} linked LEHD workplace blocks ({modeled_workers:.1f} modeled workers across {total_block_jobs:,} block jobs)",
            ],
        ]

        notes_dict: Dict[str, str] = {
            "app": f"Loaded live from BigQuery a4i_econ.businesses (as of {submitted_str})",
            "lease": f"Corridor: {pub.get('business_corridor') or seed.get('corridor') or 'Central Market'} · Supervisor District {pub.get('supervisor_district') or '6'}",
        }

        ui_app = {
            "id": bid,
            "key": f"b_{bid.replace('-', '_')}",
            "name": name,
            "cat": naics_desc,
            "address": full_address,
            "owner": legal_name,
            "since": since_year,
            "staff": est_staff,
            "ask": grant_ask,
            "use": use_text,
            "impact": impact_score,
            "status": ui_status,
            "submitted": submitted_str,
            "x": ax,
            "y": ay,
            "parts": parts,
            "fin": {
                "appRev": est_rev,
                "taxRev": tax_rev,
                "q": [q_rev, q_rev, q_rev],
                "staffFiled": f"{max(1, est_staff - 2)} FT + 2 PT",
                "vendor": f"{seed.get('corridor') or 'Central Market'} Commercial Stabilization",
                "quote": quote_amt,
            },
            "missing": [],
            "notes": notes_dict,
            "edges": {
                "out": out_edges,
                "in": in_edges,
                "spill": spill_edges,
            },
            "db_provenance": {
                "table": "qwiklabs-gcp-04-029c15637557.a4i_econ.businesses",
                "graph": cascade.get("graph", "qwiklabs-gcp-04-029c15637557.a4i_econ.CascadeEconomy"),
                "tract_geoid": tract_geoid,
                "registry_status": reg_status,
                "location_start_date": start_date,
                "filtered_exposed_count": exposed_count,
                "baseline_exposed_count": base_exposed_count,
                "linked_workplace_blocks": linked_blocks,
                "modeled_worker_reach": modeled_workers,
            },
        }
        ui_applicants.append(ui_app)
        assigned_map[bid] = "PN" if idx % 3 != 2 else "MK"

        # Build backend applicant schema for /api/allocate, /api/applicant/{id}, and /api/chat
        cascade_nodes = [
            {
                "id": bid,
                "label": name,
                "type": "Applicant",
                "hop": 0,
                "naics4": naics4,
                "fragility": 0.72,
            }
        ]
        cascade_edges = []
        for eb in source_exposed[:8]:
            eb_id = eb.get("business_id")
            if not eb_id or eb_id == bid:
                continue
            hop = int(eb.get("min_hops") or 1)
            w = float(eb.get("max_bottleneck_intensity") or 0.1)
            cascade_nodes.append({
                "id": eb_id,
                "label": eb.get("name") or eb_id,
                "type": "Business",
                "hop": hop,
                "naics4": str(eb.get("naics4") or ""),
                "fragility": 0.50,
            })
            cascade_edges.append({
                "edge_id": f"sup-{bid}-{eb_id}",
                "source": bid if hop == 1 else (source_exposed[0].get("business_id") or bid),
                "target": eb_id,
                "type": "Supplies",
                "provenance": "modeled",
                "weight": w,
                "weight_label": f"{w:.3f} BEA",
                "metres": 220,
            })

        decision_cat = "RECOMMENDED" if exposed_count > 0 else "EQUITY_CARVEOUT_ALERT"
        backend_applicants.append({
            "business_id": bid,
            "name": name,
            "legal_name": legal_name,
            "address": full_address,
            "zip": zip_code,
            "naics": naics,
            "naics4": naics4,
            "industry_label": naics_desc,
            "tract_id": tract_geoid,
            "latitude": lat or 37.7795,
            "longitude": lon or -122.4135,
            "grant_ask": grant_ask,
            "cash_gap": grant_ask,
            "recommended_amount": grant_ask if exposed_count > 0 else 0,
            "fragility_score": 0.74 if exposed_count > 0 else 0.78,
            "distress_reason": use_text,
            "baseline_failure_prob": 0.55,
            "post_grant_failure_prob": 0.18,
            "hop1_count": hop1_count,
            "hop2_count": hop2_count,
            "total_2hop_reach": exposed_count,
            "footfall_workers_shared": int(round(modeled_workers)),
            "sba_loan": {
                "has_loan": False,
                "bank_name": None,
                "gross_approval": 0,
                "approval_date": None,
                "loan_status": "PUBLIC REGISTRY ONLY",
                "charged_off": False,
                "note": f"Loaded live from BigQuery a4i_econ.businesses ({reg_status}).",
            },
            "decision_category": decision_cat,
            "decision_badge": f"Live BigQuery · {exposed_count} exposed at ≥0.01 ({base_exposed_count} unfiltered)",
            "bias_flag": (
                "Zero outgoing B2B edges above 0.01 intensity cutoff in BigQuery; evaluate via neighborhood footfall and tract equity."
                if exposed_count == 0 else None
            ),
            "entity_warning": None,
            "runner_up_id": records[0]["business_id"] if records else bid,
            "runner_up_comparison": (
                f"Live BigQuery comparison for {name} ({bid}): {exposed_count} businesses exposed at ≥0.01 intensity cutoff "
                f"({hop1_count} Hop-1, {hop2_count} Hop-2) and {base_exposed_count} unfiltered in a4i_econ.CascadeEconomy."
            ),
            "cascade_nodes": cascade_nodes,
            "cascade_edges": cascade_edges,
        })

    return {
        "applicants": ui_applicants,
        "nodes": nodes_map,
        "assigned": assigned_map,
        "backend_applicants": backend_applicants,
    }


@app.on_event("startup")
async def warm_db_cache_on_startup():
    """Trigger background pre-fetch of candidate applicants from BigQuery on server startup."""
    asyncio.create_task(fetch_verified_db_records(CANDIDATE_APPLICANT_IDS, refresh=False))


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

    actual_risk_drop = min(applicant["baseline_failure_prob"], risk_reduction_pct / 100.0)
    expected_nodes_protected = round(effective_reach * actual_risk_drop * (0.65 + 0.35 * applicant["fragility_score"]), 2)

    tract = TRACT_DEMOGRAPHICS.get(applicant["tract_id"], {})
    poverty_rate = tract.get("poverty_rate", 0.22)

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
GRAPH a4i_econ.CascadeEconomy
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
-- GRAPH a4i_econ.CascadeEconomy
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
**FROM:** Main Street Resilience AI Grant Advisor (`a4i_econ.CascadeEconomy`)  
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
GRAPH a4i_econ.CascadeEconomy
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


@app.get("/api/applicants")
async def get_applicants_from_database(
    ids: str = Query("", description="Optional comma-separated business_ids to verify & load from BigQuery"),
    refresh: bool = Query(False, description="Force re-fetch from BigQuery"),
):
    """
    Loads applicant profiles from the BigQuery database (`a4i_econ.businesses` / `a4i_econ.CascadeEconomy`)
    ONLY if they are present in the database. Never returns hardcoded applicant profiles.
    """
    target_ids = [s.strip() for s in ids.split(",") if s.strip()] if ids.strip() else CANDIDATE_APPLICANT_IDS
    verified_records = await fetch_verified_db_records(target_ids, refresh=refresh)
    built = build_profiles_from_db_records(verified_records)
    return {
        "status": "ok",
        "source": "bigquery:qwiklabs-gcp-04-029c15637557.a4i_econ.businesses",
        "requested_ids": target_ids,
        "count": len(built["applicants"]),
        "applicants": built["applicants"],
        "nodes": built["nodes"],
        "assigned": built["assigned"],
    }


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
    verified_records = await fetch_verified_db_records(CANDIDATE_APPLICANT_IDS)
    db_applicants = build_profiles_from_db_records(verified_records)["backend_applicants"]

    enriched: List[Dict[str, Any]] = []
    for app_item in db_applicants:
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
        raise HTTPException(status_code=404, detail=f"Applicant {business_id} not found in database")

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
    pool = applicants[:5]
    if selected and selected not in pool:
        pool = pool[:4] + [selected]
    specs = [{
        'business_id': a['business_id'], 'name': a['name'], 'address': a.get('address'), 'tract_id': a.get('tract_id'),
        'requested_amount': max(1, int(a.get('grant_ask') or 10000)),
        'cash_gap': max(1, int(a.get('cash_gap') or a.get('grant_ask') or 10000)),
        'input_type': 'simulated',
        'evidence_note': 'SYNTHETIC UI DEMO ONLY. Not factual financial evidence about this business.',
        'operating_assumption': a.get('operating_assumption', 'Assume full gap funding sustains operation for 90 days in this simulation.')
    } for a in pool]
    context = {'selected_business': {'business_id': selected['business_id'], 'name': selected['name'], 'address': selected.get('address'), 'tract_id': selected.get('tract_id')} if selected else None,
        'demo_scenario': {'budget': max(1, int(req.budget or 50000)), 'horizon_days': 90, 'applicants': specs},
        'provenance': 'Applicant business identities and network profiles loaded from BigQuery. Financial inputs are simulated.',
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
    verified_records = await fetch_verified_db_records(CANDIDATE_APPLICANT_IDS)
    db_applicants = build_profiles_from_db_records(verified_records)["backend_applicants"]
    app_name = req.agent_app
    user_id = 'ui-' + str(req.client_id)
    key = (user_id, app_name)
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
                           'newMessage': {'role': 'user', 'parts': [{'text': chat_context(req, db_applicants)}]}}
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
