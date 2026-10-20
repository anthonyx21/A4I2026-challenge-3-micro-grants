"""Validate graph keys/references, create metadata, and render Toolbox config."""
import argparse
from pathlib import Path
import yaml
from google.cloud import bigquery
from cascade_analyst.config import CORRIDOR, DATASET, LOCATION, PROJECT
from cascade_analyst.queries import GRAPH_DDL, SEARCH_SQL, cascade_sql


def validate(client):
    p = f"{PROJECT}.{DATASET}."
    businesses = list(client.list_rows(p + "businesses"))
    edges = list(client.list_rows(p + "supplies"))
    ids = [r["business_id"] for r in businesses]
    edge_ids = [r["edge_id"] for r in edges]
    if not ids or any(not i for i in ids) or len(ids) != len(set(ids)):
        raise ValueError("Business keys must be nonempty and unique")
    if any(not i for i in edge_ids) or len(edge_ids) != len(set(edge_ids)):
        raise ValueError("Edge keys must be nonempty and unique")
    if {r["corridor"] for r in businesses} != {CORRIDOR}:
        raise ValueError("Use one corridor per dataset and configure CORRIDOR to match it")
    for e in edges:
        if e["supplier_id"] not in ids or e["buyer_id"] not in ids:
            raise ValueError("Dangling supply endpoint")
        if e["edge_id"] != f'{e["supplier_id"]}|{e["buyer_id"]}':
            raise ValueError("Supply edge ID must encode supplier|buyer")
    print(f"Validated {len(ids)} businesses and {len(edges)} supply edges in {CORRIDOR}")


def render(path):
    docs = [{"kind": "source", "name": "economy", "type": "bigquery", "project": PROJECT,
             "location": LOCATION, "readOnly": True, "allowedDatasets": [DATASET],
             "maxQueryResultRows": 501, "maximumBytesBilled": 100 * 1024 * 1024}]
    def param(name, kind, description):
        return {"name": name, "type": kind, "description": description}
    common = {"kind": "tool", "type": "bigquery-sql", "source": "economy",
              "annotations": {"readOnlyHint": True}}
    docs.append({**common, "name": "search_businesses", "description": "Resolve corridor businesses by name or ID.",
                 "statement": SEARCH_SQL, "parameters": [param("query", "string", "Name or exact ID"), param("corridor", "string", "Selected corridor")]})
    for direction in ("supply_disruption", "customer_loss"):
        for depth in (2, 3):
            docs.append({**common, "name": f"cascade_{direction}_{depth}",
                         "description": f"Real {depth}-hop graph traversal for {direction}. Returns one shortest path per endpoint.",
                         "statement": cascade_sql(depth, direction),
                         "parameters": [param("business_id", "string", "Exact seed ID"),
                                        param("corridor", "string", "Selected corridor"),
                                        param("min_intensity", "float", "Minimum coefficient on every traversed edge")]})
    path.write_text(yaml.safe_dump_all(docs, sort_keys=False))
    print(f"Rendered {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-only", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("tools.yaml"))
    args = parser.parse_args()
    if not args.config_only:
        c = bigquery.Client(project=PROJECT, location=LOCATION)
        validate(c)
        job = c.query(GRAPH_DDL)
        job.result(timeout=90)
        print(f"Graph ready; setup job {job.job_id}")
    render(args.output)
