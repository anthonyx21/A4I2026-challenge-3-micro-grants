from .review import audit_comparison


async def review_grant_scenario(budget: float, applicants: list[dict], horizon_days: int,
                                memo_text: str = '', direction: str = 'supply_disruption',
                                min_intensity: float = 0.01) -> dict:
    """Recompute a grant scenario with live graph evidence and review consistency and optional memo wording.

    Args:
        budget: Grant budget in USD.
        applicants: Two to six objects with business_id, requested_amount, cash_gap, input_type
            (verified/applicant_reported/simulated), evidence_note, and operating_assumption.
        horizon_days: Explicit operating horizon, 1–365 days.
        memo_text: Optional draft for conservative phrase screening; empty reviews evidence only.
        direction: supply_disruption or customer_loss, kept separate.
        min_intensity: Per-edge sensitivity cutoff, not a probability.
    """
    from grant_advisor.tools import compare_applicants
    comparison = await compare_applicants(budget, applicants, horizon_days, direction, min_intensity)
    if comparison['status'] != 'ok':
        return {'status': 'blocked', 'approval_ready': False, 'cause': comparison,
                'message': 'Live evidence incomplete; no review clearance issued'}
    return {**audit_comparison(comparison, memo_text), 'comparison': comparison}
