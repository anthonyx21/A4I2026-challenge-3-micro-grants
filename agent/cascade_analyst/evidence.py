"""Deterministic summaries of graph evidence, independent of the LLM."""
import json
import math


def normalize_path(raw) -> dict:
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, list) or len(raw) < 3 or len(raw) % 2 != 1:
        raise ValueError("Expected alternating BigQuery graph node/edge JSON")
    nodes, edges = [], []
    for i, element in enumerate(raw):
        expected = "node" if i % 2 == 0 else "edge"
        if element.get("kind") != expected:
            raise ValueError("Malformed graph path")
        props = element["properties"]
        if expected == "node":
            nodes.append({k: props[k] for k in ("business_id", "name", "naics4", "corridor")})
        else:
            weight = float(props["intensity"])
            metres = float(props["metres"])
            if not math.isfinite(weight) or weight < 0 or not math.isfinite(metres) or metres < 0:
                raise ValueError("Invalid edge attributes")
            edges.append({"edge_id": props["edge_id"], "intensity": weight, "metres": metres,
                          "supplier_id": props["edge_id"].split("|")[0],
                          "buyer_id": props["edge_id"].split("|")[-1], "evidence": "modeled"})
    ids = [n["business_id"] for n in nodes]
    if len(set(ids)) != len(ids):
        raise ValueError("Cycle in shortest path evidence")
    return {"nodes": nodes, "edges": edges, "hops": len(edges),
            "bottleneck_intensity": min(e["intensity"] for e in edges),
            "path": " → ".join(n["name"] for n in nodes)}


def summarize(rows: list[dict], seed_id: str) -> dict:
    paths = {}
    for row in rows:
        p = normalize_path(row["path"])
        if p["nodes"][0]["business_id"] != seed_id:
            raise ValueError("Path seed does not match request")
        endpoint = p["nodes"][-1]["business_id"]
        if endpoint != row["exposed_id"]:
            raise ValueError("Path endpoint does not match query result")
        if endpoint == seed_id:
            continue
        previous = paths.get(endpoint)
        if previous is None or p["hops"] < previous["hops"]:
            paths[endpoint] = p
    ordered = sorted(paths.values(), key=lambda p: (p["hops"], -p["bottleneck_intensity"], p["nodes"][-1]["business_id"]))
    direct = sum(p["hops"] == 1 for p in ordered)
    return {"exposed_business_count": len(ordered), "direct_count": direct,
            "multi_hop_count": len(ordered) - direct,
            "exposed_businesses": [p["nodes"][-1] for p in ordered],
            "example_paths": ordered[:8],
            "path_selection": "One arbitrary shortest path per endpoint; examples favor fewer hops then stronger bottlenecks. Not the strongest possible path."}


def compare(baseline: dict, filtered: dict) -> dict:
    base = {b["business_id"] for b in baseline["exposed_businesses"]}
    remaining = {b["business_id"] for b in filtered["exposed_businesses"]}
    if not remaining <= base:
        raise ValueError("Filtered reachability must be a subset of baseline")
    return {"baseline_count": len(base), "filtered_count": len(remaining),
            "removed_count": len(base - remaining), "retained_fraction": len(remaining) / len(base) if base else None,
            "removed_business_ids": sorted(base - remaining),
            "method": "Re-traverse after removing every edge below the threshold; alternate qualifying paths remain eligible."}
