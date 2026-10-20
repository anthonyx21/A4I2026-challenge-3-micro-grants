"""Fixed, parameterized queries. The model never supplies SQL."""
from .config import DATASET, GRAPH, PROJECT

GRAPH_DDL = f"""
CREATE PROPERTY GRAPH IF NOT EXISTS {DATASET}.{GRAPH}
NODE TABLES (
  {DATASET}.businesses KEY (business_id)
  LABEL Business PROPERTIES (business_id, name, naics4, corridor, latitude, longitude)
)
EDGE TABLES (
  {DATASET}.supplies KEY (edge_id)
  SOURCE KEY (supplier_id) REFERENCES businesses (business_id)
  DESTINATION KEY (buyer_id) REFERENCES businesses (business_id)
  LABEL Supplies PROPERTIES (edge_id, intensity, metres)
)
"""

SEARCH_SQL = f"""
SELECT business_id, name, naics4, corridor
FROM `{PROJECT}.{DATASET}.businesses`
WHERE corridor = @corridor
  AND (business_id = @query OR STRPOS(LOWER(name), LOWER(@query)) > 0)
ORDER BY IF(business_id = @query OR LOWER(name) = LOWER(@query), 0, 1), name, business_id
LIMIT 21
"""


def cascade_sql(depth: int, direction: str) -> str:
    if depth not in (2, 3) or direction not in ("supply_disruption", "customer_loss"):
        raise ValueError("Unsupported traversal")
    edge = "-[e:Supplies WHERE e.intensity >= @min_intensity]->" if direction == "supply_disruption" else "<-[e:Supplies WHERE e.intensity >= @min_intensity]-"
    return f"""
GRAPH {DATASET}.{GRAPH}
MATCH p = ANY SHORTEST (seed:Business WHERE seed.business_id = @business_id AND seed.corridor = @corridor)
  {edge}{{1,{depth}}}(exposed:Business)
WHERE exposed.business_id != seed.business_id AND exposed.corridor = @corridor
RETURN exposed.business_id AS exposed_id, exposed.name AS exposed_name, TO_JSON(p) AS path
ORDER BY exposed_id
LIMIT 501
"""
