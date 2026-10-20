"""Dated registry status and county WARN context, consumed through Google's MCP Toolbox."""
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from cascade_analyst.config import CORRIDOR, PROJECT, DATASET, TOOLBOX_URL
from cascade_analyst.tools import _call, error_message


def summarize_public_records(business_id, status_rows, warn_rows):
    if len(status_rows)>500 or len(warn_rows)>500:
        raise ValueError('Public records truncated')
    if any(r['business_id']!=business_id for r in status_rows):
        raise ValueError('Registry location ID mismatch')
    if len({r['record_id'] for r in status_rows})!=len(status_rows):
        raise ValueError('Duplicate registry record keys')
    as_of=max((r['source_as_of'] for r in status_rows if r.get('source_as_of')),default=None)
    latest=[r for r in status_rows if r.get('source_as_of')==as_of]
    open_records=[r for r in latest if not r.get('location_end_date') and not r.get('administratively_closed')]
    ended=[r for r in latest if r.get('location_end_date') or r.get('administratively_closed')]
    status=('no_matching_record' if not latest else 'mixed_registry_records' if open_records and ended else
            'closure_recorded' if ended else 'no_closure_recorded')
    return {'status':'ok','business_id':business_id,'corridor':CORRIDOR,'registry_status':status,
            'registry_source_as_of':as_of,'registry_records':status_rows,
            'warn_scope':'San Francisco County; no verified business or corridor link',
            'warn_notices':warn_rows,'warn_notice_count':len(warn_rows),
            'source_tables':[f'{PROJECT}.{DATASET}.{n}' for n in ('public_business_status','public_warn_notices')],
            'limitations':['Registry rows match exact location ID; multiple ownership records may have different closure histories.',
                           'No recorded closure does not verify present operation or financial health. Registry dates may lag reality.',
                           'WARN is a dated county snapshot of reported events, not all closures, and effective dates are announced dates, not verified outcomes.',
                           'WARN employers have not been matched to corridor businesses or workplace blocks; do not create an anchor cascade from these notices alone.',
                           'WARN employee counts are affected employees in notices, not business graph employment or jobs saved. Do not sum duplicate/revised events as unique workers.',
                           'These sources contain no grant applications, current cash gaps, observed supply transactions or proven grant effects.']}


async def get_public_business_context(business_id: str) -> dict:
    """Retrieve exact-ID DataSF status records and separately scoped SF County WARN notices.

    Args:
        business_id: Exact corridor business ID returned by search_businesses.
    """
    if not isinstance(business_id,str) or not business_id.strip() or len(business_id)>200:
        return {'status':'invalid_input','message':'Supply an exact business ID'}
    try:
        async with asyncio.timeout(90):
            async with streamablehttp_client(f'{TOOLBOX_URL}/mcp') as (read,write,_):
                async with ClientSession(read,write) as session:
                    await session.initialize()
                    seeds=await _call(session,'search_businesses',{'query':business_id,'corridor':CORRIDOR})
                    if not any(r['business_id']==business_id for r in seeds):
                        return {'status':'not_found','message':'Business not in selected corridor'}
                    status=await _call(session,'public_business_status',{'business_id':business_id,'corridor':CORRIDOR})
                    warn=await _call(session,'public_warn_context',{})
        return summarize_public_records(business_id,status,warn)
    except Exception as exc:
        return {'status':'unavailable','message':error_message(exc),
                'action':'Check public snapshot load and MCP configuration; do not infer status or WARN matches.'}
