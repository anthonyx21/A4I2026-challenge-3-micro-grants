"""Transparent scenario allocation; no inferred financial need or causal claims."""
from decimal import Decimal, InvalidOperation
from itertools import combinations


def cents(value) -> int:
    try:
        amount = Decimal(str(value))
        valid = amount.is_finite() and amount > 0 and amount == amount.quantize(Decimal('.01'))
    except InvalidOperation as exc:
        raise ValueError("Amounts must be numeric") from exc
    if not valid:
        raise ValueError("Amounts must be positive with at most two decimal places")
    return int(amount * 100)


def validate(budget, applicants, horizon_days):
    fund = cents(budget)
    if not isinstance(horizon_days, int) or isinstance(horizon_days, bool) or not 1 <= horizon_days <= 365:
        raise ValueError("Specify an operating horizon from 1 to 365 days")
    if not isinstance(applicants, list) or not 2 <= len(applicants) <= 6:
        raise ValueError("Supply two to six applicants for a comparison")
    clean = []
    for a in applicants:
        if not isinstance(a, dict):
            raise ValueError("Each applicant must be an object")
        id = a.get('business_id', '')
        if not isinstance(id, str):
            raise ValueError("Business IDs must be strings")
        id = id.strip()
        if not id or id in {r['business_id'] for r in clean}:
            raise ValueError("Applicant business IDs must be present and unique")
        source = a.get('input_type')
        if source not in ('applicant_reported', 'verified', 'simulated'):
            raise ValueError("Label input_type as applicant_reported, verified, or simulated")
        evidence = a.get('evidence_note')
        assumption = a.get('operating_assumption')
        if not isinstance(evidence, str) or not evidence.strip() or not isinstance(assumption, str) or not assumption.strip():
            raise ValueError("Each applicant needs an evidence_note and operating_assumption explaining what funding changes")
        clean.append({'business_id': id, 'input_type': source, 'evidence_note': evidence.strip(),
                      'operating_assumption': assumption.strip(),
                      'cash_gap': cents(a.get('cash_gap')) / 100, 'requested_amount': cents(a.get('requested_amount')) / 100,
                      'gap_cents': cents(a.get('cash_gap')), 'request_cents': cents(a.get('requested_amount'))})
    return fund, clean


def allocate(fund: int, candidates: list[dict]) -> dict:
    """Enumerate feasible grant portfolios; maximize unique filtered modeled exposure."""
    eligible = [c for c in candidates if c['gap_cents'] <= c['request_cents'] and c['gap_cents'] <= fund]
    portfolios = []
    for size in range(1, len(eligible) + 1):
        for group in combinations(eligible, size):
            cost = sum(c['gap_cents'] for c in group)
            if cost > fund:
                continue
            seeds = {c['business_id'] for c in group}
            filtered = set().union(*(set(c['filtered_ids']) for c in group)) - seeds
            baseline = set().union(*(set(c['baseline_ids']) for c in group)) - seeds
            portfolios.append({'business_ids': sorted(seeds), 'amount': cost / 100,
                               'filtered_exposed_ids': sorted(filtered), 'baseline_exposed_ids': sorted(baseline),
                               'filtered_exposure_count': len(filtered), 'baseline_exposure_count': len(baseline)})
    def ranking(p, field):
        return (-p[field], p['amount'], p['business_ids'])
    portfolios.sort(key=lambda p: ranking(p, 'filtered_exposure_count'))
    baseline_order = sorted(portfolios, key=lambda p: ranking(p, 'baseline_exposure_count'))
    best = portfolios[0] if portfolios else None
    # A zero-exposure graph supplies no network reason to prefer a grant.
    if best and best['filtered_exposure_count'] == 0:
        best = None
    alternative = next((p for p in portfolios if best and p['business_ids'] != best['business_ids']), None)
    base = baseline_order[0] if baseline_order else None
    return {'recommendation': best, 'runner_up': alternative,
            'baseline_choice': base,
            'choice_changes_without_edge_filter': bool(best and base and best['business_ids'] != base['business_ids']),
            'feasible_portfolios': len(portfolios),
            'unallocated_amount': (fund - round(best['amount'] * 100)) / 100 if best else fund / 100,
            'objective': 'Maximize unique reachable businesses after filtering weak modeled links; ties use lower total grant then business ID.',
            'amount_rule': 'Fund the supplied cash gap in full, capped by requested amount and budget. No assumed benefit from partial grants.',
            'interpretation': 'Scenario allocation conditional on supplied operating assumptions; not a causal impact forecast or a grant approval.'}
