"""Collect specialist evidence and compare budget-feasible interventions."""
import asyncio
import math
from cascade_analyst.tools import analyze_cascade
from cascade_analyst.config import CORRIDOR
from cascade_analyst.queries import cascade_sql
from neighborhood_context.tools import get_neighborhood_context
from .decision import allocate, validate
from neighborhood_context.public_records import get_public_business_context


async def compare_applicants(budget: float, applicants: list[dict], horizon_days: int,
                             direction: str = 'supply_disruption', min_intensity: float = 0.01) -> dict:
    """Compare two to six applicants using supplied needs and live Cascade Analyst evidence.

    Args:
        budget: Available grant fund, in USD.
        applicants: Objects with business_id, requested_amount, cash_gap, input_type
            (verified, applicant_reported, or simulated), evidence_note and operating_assumption.
            The operating assumption states how full gap funding sustains operation for horizon_days.
        horizon_days: Explicit assumed operating period, 1–365 days.
        direction: supply_disruption or customer_loss; never combine the mechanisms in one score.
        min_intensity: Per-edge sensitivity threshold, default 0.01; not a probability.
    """
    try:
        fund, clean = validate(budget, applicants, horizon_days)
        if direction not in ('supply_disruption', 'customer_loss') or not math.isfinite(min_intensity) or not 0 <= min_intensity <= 1:
            raise ValueError('Use a supported mechanism and finite threshold 0–1')
    except (ValueError, TypeError, KeyError) as exc:
        return {'status': 'needs_input', 'message': str(exc)}
    results = []
    try:
        async with asyncio.timeout(240):
            for applicant in clean:
                evidence = await analyze_cascade(applicant['business_id'], direction, 2, min_intensity)
                if evidence['status'] != 'ok':
                    return {'status': 'incomplete', 'business_id': applicant['business_id'], 'cause': evidence,
                            'message': 'Cannot compare the complete shortlist. No funding recommendation issued.'}
                public = await get_public_business_context(applicant['business_id'])
                results.append({**applicant, 'name': evidence['seed']['name'],
                                'address': evidence['seed'].get('address'),
                                'cascade': evidence, 'public_records': public,
                                'baseline_ids': [b['business_id'] for b in evidence['baseline']['exposed_businesses']],
                                'filtered_ids': [b['business_id'] for b in evidence['filtered']['exposed_businesses']]})
    except TimeoutError:
        return {'status': 'incomplete', 'message': 'Analysis timed out; no complete comparison or funding recommendation issued.'}
    decision = allocate(fund, results)
    selected = set((decision['recommendation'] or {}).get('business_ids', []))
    target_ids = set(selected) | set((decision.get('runner_up') or {}).get('business_ids', []))
    if not target_ids and results:
        target_ids = {results[0]['business_id']}
    for r in results:
        r['grant_amount'] = r['gap_cents'] / 100 if r['business_id'] in selected else 0
        r['eligibility'] = 'eligible' if r['gap_cents'] <= min(r['request_cents'], fund) else 'gap_exceeds_request_or_budget'
        r.pop('gap_cents'); r.pop('request_cents'); r.pop('baseline_ids'); r.pop('filtered_ids')
        if r['business_id'] in target_ids and r['cascade'].get('graph'):
            ctx = await get_neighborhood_context(r['business_id'])
            if ctx.get('status') == 'ok':
                r['neighborhood_context'] = ctx
    simulated = any(a['input_type'] == 'simulated' for a in clean)
    report = {'status': 'ok', 'decision_scope': 'simulated_scenario' if simulated else 'conditional_decision_support',
            'corridor': CORRIDOR, 'budget': fund / 100, 'horizon_days': horizon_days,
            'direction': direction, 'min_intensity': min_intensity,
            'gql_traversal': cascade_sql(2, direction).strip(),
            'applicants': results, **decision,
            'limitations': ['Financial need and operating assumptions are supplied inputs; not inferred from BigQuery.',
                           'All supply links are modeled from industry averages and proximity, not observed transactions.',
                           'Do not claim predicted closures, jobs saved, calibrated risk probabilities or proven grant effects.',
                           'This policy compares network exposure conditional on need and operation assumptions; it does not evaluate replacement suppliers, cultural value or neighborhood equity.',
                           'Reported or verified labels describe user-supplied provenance; the agent has not independently audited documents.']
                          + (['SIMULATED: Financial scenarios attached to real names are not facts about these businesses.'] if simulated else [])}
    from evidence_reviewer.review import audit_comparison
    report['evidence_review'] = audit_comparison(report)
    return report
