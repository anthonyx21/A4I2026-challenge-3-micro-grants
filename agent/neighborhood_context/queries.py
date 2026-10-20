"""Fixed contextual queries; no model-generated SQL or demographic scoring."""
from cascade_analyst.config import PROJECT, DATASET

FOOTFALL_SQL = f"""
SELECT LPAD(CAST(e.tract AS STRING), 11, '0') AS tract_id,
       COUNT(*) AS edge_count, COUNT(DISTINCT e.block_id) AS block_count,
       SUM(f.worker_share) AS modeled_worker_allocation,
       SUM(e.jobs) AS linked_block_jobs,
       MIN(f.metres) AS min_approx_metres, MAX(f.metres) AS max_approx_metres
FROM `{PROJECT}.{DATASET}.draws_footfall_from` f
JOIN `{PROJECT}.{DATASET}.employer_blocks` e ON e.block_id = f.block_id
JOIN `{PROJECT}.{DATASET}.businesses` b ON b.business_id = f.business_id
WHERE f.business_id = @business_id AND b.corridor = @corridor
GROUP BY tract_id
ORDER BY tract_id
LIMIT 501
"""

DEMOGRAPHICS_SQL = f"""
SELECT LPAD(CAST(geo_id AS STRING), 11, '0') AS tract_id,
       total_pop, median_income, poverty_rate, no_vehicle_rate, assistance_rate
FROM `{PROJECT}.{DATASET}.tract_demographics`
ORDER BY tract_id
LIMIT 501
"""
