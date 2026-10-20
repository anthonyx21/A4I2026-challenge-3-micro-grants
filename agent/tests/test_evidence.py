import json
import pytest
from cascade_analyst.evidence import compare, normalize_path, summarize
from cascade_analyst.tools import result_rows
from cascade_analyst.queries import cascade_sql
from mcp.types import CallToolResult, TextContent


def node(id):
    return {"kind": "node", "properties": {"business_id": id, "name": id, "naics4": "7225", "corridor": "Central Market"}}


def edge(a, b, weight):
    return {"kind": "edge", "properties": {"edge_id": f"{a}|{b}", "intensity": weight, "metres": 100}}


def row(ids, weights):
    path = [node(ids[0])]
    for a, b, w in zip(ids, ids[1:], weights):
        path.extend([edge(a, b, w), node(b)])
    return {"exposed_id": ids[-1], "path": path}


def test_unique_endpoints_not_path_count():
    rows = [row(["s", "a"], [.2]), row(["s", "b", "a"], [.3, .1]), row(["s", "b", "c"], [.3, .1])]
    result = summarize(rows, "s")
    assert result["exposed_business_count"] == 2
    assert result["direct_count"] == 1
    assert result["multi_hop_count"] == 1
    assert result["example_paths"][1]["bottleneck_intensity"] == .1


def test_sensitivity_uses_retraversed_alternate_path():
    base = summarize([row(["s", "a", "x"], [.001, .2])], "s")
    filtered = summarize([row(["s", "b", "x"], [.1, .2])], "s")
    assert compare(base, filtered)["removed_count"] == 0
    assert compare(base, summarize([], "s"))["removed_count"] == 1


def test_reject_cycles_and_wrong_seed():
    with pytest.raises(ValueError):
        normalize_path(row(["s", "a", "s"], [.1, .1])["path"])
    with pytest.raises(ValueError):
        summarize([row(["different", "x"], [.1])], "s")


def test_reverse_path_keeps_edge_direction():
    r = row(["buyer", "supplier"], [.2])
    r["path"][1] = edge("supplier", "buyer", .2)
    p = normalize_path(json.dumps(r["path"]))
    assert p["edges"][0]["supplier_id"] == "supplier"
    assert p["nodes"][0]["business_id"] == "buyer"


def test_mcp_decode_and_errors():
    r = CallToolResult(content=[TextContent(type="text", text='[{"exposed_id":"a"}]')])
    assert result_rows(r) == [{"exposed_id": "a"}]
    with pytest.raises(RuntimeError):
        result_rows(CallToolResult(isError=True, content=[TextContent(type="text", text="query failed")]))


def test_queries_have_real_multihop_and_edge_filter():
    for direction in ("supply_disruption", "customer_loss"):
        sql = cascade_sql(2, direction)
        assert "ANY SHORTEST" in sql and "{1,2}" in sql and "@min_intensity" in sql
        assert "TO_JSON(p)" in sql and "@business_id" in sql
    with pytest.raises(ValueError):
        cascade_sql(99, "supply_disruption")


def test_toolbox_empty_query_is_not_an_outage():
    r = CallToolResult(content=[TextContent(type="text", text=json.dumps("The query returned 0 rows."))])
    assert result_rows(r) == []
