"""Fixed public-record queries; no fuzzy business-to-WARN attribution."""
from cascade_analyst.config import PROJECT, DATASET

STATUS_SQL = f"""
SELECT s.*
FROM `{PROJECT}.{DATASET}.public_business_status` s
JOIN `{PROJECT}.{DATASET}.businesses` b ON b.business_id = s.business_id
WHERE b.business_id = @business_id AND b.corridor = @corridor
ORDER BY s.source_as_of DESC, s.record_id
LIMIT 501
"""

WARN_SQL = f"""
SELECT * FROM `{PROJECT}.{DATASET}.public_warn_notices`
WHERE county = 'San Francisco County'
ORDER BY effective_date DESC, notice_id
LIMIT 501
"""
