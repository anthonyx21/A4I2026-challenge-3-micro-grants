"""Live MCP integration check, without a model call."""
import asyncio
import json
from cascade_analyst.tools import analyze_cascade, search_businesses


async def main():
    result = await search_businesses("Steel + Lacquer")
    assert result["status"] == "ok", result
    seed = next(b for b in result["matches"] if b["name"] == "Steel + Lacquer")
    report = await analyze_cascade(seed["business_id"])
    assert report["status"] == "ok", report
    assert report["baseline"]["multi_hop_count"] > 0, report
    assert report["sensitivity"]["filtered_count"] <= report["sensitivity"]["baseline_count"]
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
