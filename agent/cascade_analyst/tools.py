"""Custom ADK tools consuming Google's MCP Toolbox over Streamable HTTP."""
import asyncio
import json
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from .config import CORRIDOR, DATASET, GRAPH, PROJECT, TOOLBOX_URL
from .evidence import compare, summarize
from .queries import cascade_sql


def result_rows(result) -> list[dict]:
    if result.isError:
        raise RuntimeError("; ".join(c.text for c in result.content if hasattr(c, "text")))
    rows = []
    for block in result.content:
        if hasattr(block, "text"):
            value = json.loads(block.text)
            if isinstance(value, list):
                rows.extend(value)
            elif isinstance(value, dict):
                rows.append(value)
            elif value == "The query returned 0 rows.":
                continue
            else:
                raise ValueError("Unexpected MCP result shape")
    return rows


def error_message(exc: BaseException) -> str:
    if isinstance(exc, BaseExceptionGroup):
        return "; ".join(error_message(e) for e in exc.exceptions)
    return str(exc) or type(exc).__name__


async def _call(session, name, params):
    return result_rows(await session.call_tool(name, params))


async def search_businesses(query: str) -> dict:
    """Find a Central Market business by name or exact ID. Return candidates; never guess between ambiguous matches."""
    if not query.strip() or len(query) > 200:
        return {"status": "invalid_input", "message": "Enter a name or business ID (1–200 characters)."}
    try:
        async with asyncio.timeout(90):
            async with streamablehttp_client(f"{TOOLBOX_URL}/mcp") as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    rows = await _call(session, "search_businesses", {"query": query.strip(), "corridor": CORRIDOR})
        return {"status": "ok", "corridor": CORRIDOR, "matches": rows[:20], "truncated": len(rows) > 20}
    except Exception as exc:
        return {"status": "unavailable", "message": error_message(exc), "action": "Check Toolbox, ADC and BigQuery access. Do not invent matches."}


async def analyze_cascade(business_id: str, direction: str = "supply_disruption", depth: int = 2, min_intensity: float = 0.01) -> dict:
    """Trace actual two/three-hop graph paths for a business and re-traverse without weak modeled links.

    Args:
        business_id: Exact ID returned by search_businesses.
        direction: supply_disruption follows supplier to buyer; customer_loss follows buyer to supplier.
        depth: Two by default. Three is exploratory and may saturate the corridor.
        min_intensity: Sensitivity cutoff per edge, between 0 and 1; this is not a probability.
    """
    if direction not in ("supply_disruption", "customer_loss") or depth not in (2, 3) or not 0 <= min_intensity <= 1:
        return {"status": "invalid_input", "message": "Use a supported direction, depth 2 or 3, and threshold 0–1."}
    try:
        async with asyncio.timeout(180):
            async with streamablehttp_client(f"{TOOLBOX_URL}/mcp") as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    seeds = await _call(session, "search_businesses", {"query": business_id, "corridor": CORRIDOR})
                    seed = next((b for b in seeds if b["business_id"] == business_id), None)
                    if seed is None:
                        return {"status": "not_found", "message": "Business ID is not in the selected corridor."}
                    params = {"business_id": business_id, "corridor": CORRIDOR, "min_intensity": 0.0}
                    name = f"cascade_{direction}_{depth}"
                    raw = await _call(session, name, params)
                    params["min_intensity"] = min_intensity
                    filtered_raw = await _call(session, name, params)
        if len(raw) > 500 or len(filtered_raw) > 500:
            return {"status": "incomplete", "message": "Result exceeds 500 endpoints. No complete exposure count claimed; narrow corridor or depth."}
        baseline, filtered = summarize(raw, business_id), summarize(filtered_raw, business_id)
        return {"status": "ok", "seed": seed, "direction": direction, "depth": depth,
                "graph": f"{PROJECT}.{DATASET}.{GRAPH}", "gql_query": cascade_sql(depth, direction).strip(),
                "baseline": baseline, "filtered": filtered,
                "sensitivity": {"min_intensity": min_intensity, **compare(baseline, filtered)},
                "warnings": ["Supply links are modeled from industry coefficients and proximity, not observed transactions.",
                             "Reachability is potential exposure, not predicted closures, business employment or jobs saved.",
                             "No closure probability, financial need, substitution behavior or grant effect is established.",
                             "Customer-loss paths represent upstream demand exposure; their coefficients are not supplier revenue shares."]
                            + (["Three-hop reachability can saturate the corridor; compare with two hops."] if depth == 3 else [])}
    except Exception as exc:
        return {"status": "unavailable", "message": error_message(exc),
                "action": "Check Toolbox, ADC, graph setup and Enterprise reservation. Do not replace a failed graph query with invented analysis."}
