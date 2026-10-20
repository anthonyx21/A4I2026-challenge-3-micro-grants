"""Authenticated Cloud Run ingress: ADK API and chat UI."""
import os
from google.adk.cli.fast_api import get_fast_api_app
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from fastapi import HTTPException

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
