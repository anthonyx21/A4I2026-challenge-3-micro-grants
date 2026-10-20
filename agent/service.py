"""Authenticated Cloud Run ingress: ADK API and chat UI."""
import os
from google.adk.cli.fast_api import get_fast_api_app
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from fastapi import HTTPException

from cascade_analyst.tools import analyze_cascade, search_businesses
from neighborhood_context.tools import get_neighborhood_context
from neighborhood_context.public_records import get_public_business_context

CANDIDATE_APPLICANT_IDS = [
    "1026779-04-151",
    "0111663-06-001",
    "1402027-10-251",
    "1051330-01-161",
    "1188036-05-181",
    "1056704-02-161",
    "1080659-07-161",
    "1373515-10-241",
]

app = get_fast_api_app(
    agents_dir="/app", web=True, use_local_storage=False,
    host="0.0.0.0", port=int(os.environ.get("PORT", "8080")),
    reload_agents=False, max_llm_calls=16,
)


@app.get("/api/health")
async def health():
    try:
        async with streamablehttp_client("http://127.0.0.1:5000/mcp") as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
        return {"status": "ok", "agents": ["corridor_coordinator", "cascade_analyst", "grant_advisor", "evidence_reviewer", "neighborhood_context"], "mcp": "ready"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="MCP Toolbox unavailable") from exc


@app.get("/api/applicants")
async def get_applicants(ids: str = ""):
    """Load applicant profiles from BigQuery only if present in the database."""
    target_ids = [s.strip() for s in ids.split(",") if s.strip()] if ids else CANDIDATE_APPLICANT_IDS
    present_applicants = []
    for bid in target_ids:
        found = await search_businesses(bid)
        matches = found.get("matches") or []
        exact = next((m for m in matches if m.get("business_id") == bid), None)
        if not exact:
            continue
        cascade = await analyze_cascade(bid, min_intensity=0.01)
        if cascade.get("status") != "ok":
            continue
        pub = await get_public_business_context(bid)
        nh = await get_neighborhood_context(bid)
        present_applicants.append({
            "business_id": bid,
            "business": exact,
            "cascade": cascade,
            "public_context": pub if pub.get("status") == "ok" else {},
            "neighborhood_context": nh if nh.get("status") == "ok" else {},
        })
    return {"status": "ok", "count": len(present_applicants), "applicants": present_applicants}
