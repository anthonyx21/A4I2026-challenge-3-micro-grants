"""MCP-backed worker and tract context, kept separate from grant allocation."""
import asyncio
import math
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from cascade_analyst.config import CORRIDOR, PROJECT, DATASET, TOOLBOX_URL
from cascade_analyst.tools import _call, error_message


def summarize_context(seed: dict, footfall: list[dict], demographics: list[dict]) -> dict:
    if len(footfall) > 500 or len(demographics) > 500:
        raise ValueError('Context truncated; no complete summary issued')
    ids = [d['tract_id'] for d in demographics]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate demographic tract keys')
    for d in demographics:
        for key in ('poverty_rate', 'no_vehicle_rate', 'assistance_rate'):
            value = d.get(key)
            if value is not None and (not math.isfinite(value) or not 0 <= value <= 1):
                raise ValueError('Demographic rates must be fractions between zero and one')
    tract_map = {d['tract_id']: d for d in demographics}
    linked = []
    for row in footfall:
        if row['edge_count'] != row['block_count']:
            raise ValueError('Duplicate block/business edges would inflate worker context')
        if not math.isfinite(row['modeled_worker_allocation']) or row['modeled_worker_allocation'] < 0:
            raise ValueError('Invalid worker allocation')
        linked.append({**row, 'demographics': tract_map.get(row['tract_id']),
                       'demographic_match': row['tract_id'] in tract_map})
    return {'status': 'ok', 'seed': seed, 'corridor': CORRIDOR,
            'source_tables': [f'{PROJECT}.{DATASET}.{n}' for n in
                              ('draws_footfall_from', 'employer_blocks', 'tract_demographics')],
            'footfall_status': 'modeled_links_present' if footfall else 'no_modeled_links',
            'modeled_worker_allocation': sum(r['modeled_worker_allocation'] for r in footfall),
            'linked_block_count': sum(r['block_count'] for r in footfall),
            'linked_block_jobs': sum(r['linked_block_jobs'] for r in footfall),
            'linked_tracts': linked, 'dataset_tract_context': demographics,
            'missing_demographic_tracts': [r['tract_id'] for r in linked if not r['demographic_match']],
            'limitations': [
                'worker_share is fractional modeled nearby demand allocation, not business employment, actual visits or jobs saved.',
                'Linked-block jobs describe workplace census blocks, not identified employers or jobs at this business.',
                'Block coordinates are approximated to tract internal points; model allocates workers equally across consumer businesses within 500 metres.',
                'Demographic rates are fractions: poverty among people with determined poverty status; vehicle access and assistance among households.',
                'Tracts describe contextual populations, not verified customers or the business location. No tract geometry is queried here.',
                'No modeled footfall links does not establish no customers or no community value.',
                'Do not sum allocations across independently queried businesses as unique workers; shared blocks overlap.',
                'Do not average tract medians or infer corridor rates: source denominators and vintage metadata are not stored in these tables.',
                'Context informs questions for a human officer; no demographic score or funding ranking is produced.']}


async def get_neighborhood_context(business_id: str) -> dict:
    """Fetch modeled worker links and per-tract public context for a resolved business ID.

    Args:
        business_id: Exact ID returned by search_businesses. No location or customer tract is inferred.
    """
    if not isinstance(business_id, str) or not business_id.strip() or len(business_id) > 200:
        return {'status': 'invalid_input', 'message': 'Supply an exact business ID'}
    try:
        async with asyncio.timeout(120):
            async with streamablehttp_client(f'{TOOLBOX_URL}/mcp') as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    seeds = await _call(session, 'search_businesses', {'query': business_id, 'corridor': CORRIDOR})
                    seed = next((b for b in seeds if b['business_id'] == business_id), None)
                    if seed is None:
                        return {'status': 'not_found', 'message': 'Business is not in the selected corridor'}
                    footfall = await _call(session, 'business_footfall_context', {'business_id': business_id, 'corridor': CORRIDOR})
                    demographics = await _call(session, 'dataset_tract_context', {})
        return summarize_context(seed, footfall, demographics)
    except Exception as exc:
        return {'status': 'unavailable', 'message': error_message(exc),
                'action': 'Check read-only MCP queries and table access. Do not invent neighborhood evidence.'}
