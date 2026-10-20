"""Deterministic checks of calculator output; review does not approve a grant."""
import re
from decimal import Decimal, InvalidOperation


def audit_comparison(comparison: dict, memo_text: str = '') -> dict:
    findings = []
    def flag(code, severity, message):
        findings.append({'code': code, 'severity': severity, 'message': message})
    if comparison.get('status') != 'ok':
        return {'status': 'blocked', 'findings': [{'code': 'INCOMPLETE_EVIDENCE', 'severity': 'error',
                'message': 'Complete successful comparison required; no review clearance issued.'}],
                'approval_ready': False}
    try:
        applicants = comparison['applicants']
        ids = [a['business_id'] for a in applicants]
        if len(set(ids)) != len(ids): flag('DUPLICATE_APPLICANTS', 'error', 'Applicant IDs repeat')
        simulated = any(a['input_type'] == 'simulated' for a in applicants)
        if simulated:
            flag('SIMULATED_INPUTS', 'warning', 'Financial inputs are synthetic; this is a demo, not a real funding assessment')
        if simulated and comparison.get('decision_scope') != 'simulated_scenario':
            flag('PROVENANCE_MISMATCH', 'error', 'Simulated applicants require simulated scenario scope')
        for a in applicants:
            if not a.get('evidence_note') or not a.get('operating_assumption'):
                flag('MISSING_INPUT_EVIDENCE', 'error', 'Missing financial evidence note or intervention assumption')
            cascade = a['cascade']
            if cascade.get('status') != 'ok': flag('CASCADE_FAILED', 'error', 'An applicant cascade is incomplete')
            if 'filtered' in cascade and 'exposed_businesses' in cascade['filtered']:
                exposed = {b['business_id'] for b in cascade['filtered']['exposed_businesses']}
                if cascade['filtered'].get('exposed_business_count') != len(exposed):
                    flag('CASCADE_COUNT_MISMATCH', 'error', 'Filtered endpoint count disagrees with identities')
        choice = comparison.get('recommendation')
        grants = [Decimal(str(a.get('grant_amount', 0))) for a in applicants]
        budget = Decimal(str(comparison['budget']))
        if not budget.is_finite() or budget <= 0 or any(not g.is_finite() or g < 0 for g in grants):
            raise ValueError('Invalid money values')
        spend = sum(grants)
        if spend > budget: flag('BUDGET_EXCEEDED', 'error', 'Grant total exceeds available budget')
        if spend + Decimal(str(comparison['unallocated_amount'])) != budget:
            flag('BUDGET_RECONCILIATION', 'error', 'Grants and unallocated budget do not reconcile')
        if choice:
            selected = set(choice['business_ids'])
            if not selected <= set(ids): flag('UNKNOWN_RECIPIENT', 'error', 'Recipient is absent from shortlist')
            if spend != Decimal(str(choice['amount'])):
                flag('ALLOCATION_MISMATCH', 'error', 'Portfolio amount disagrees with applicant grants')
            union = set()
            for a, grant in zip(applicants, grants):
                if a['business_id'] in selected:
                    if grant != Decimal(str(a['cash_gap'])) or grant > Decimal(str(a['requested_amount'])):
                        flag('GRANT_NEED_MISMATCH', 'error', 'Grant must fully fund supplied gap within the request')
                    union.update(b['business_id'] for b in a['cascade']['filtered']['exposed_businesses'])
                elif grant != 0: flag('UNSELECTED_GRANT', 'error', 'Unselected applicant has a grant')
            union -= selected
            if choice['filtered_exposure_count'] != len(union) or set(choice['filtered_exposed_ids']) != union:
                flag('PORTFOLIO_COUNT_MISMATCH', 'error', 'Portfolio exposure must be deduplicated and exclude funded seeds')
        elif spend != 0:
            flag('GRANTS_WITHOUT_RECOMMENDATION', 'error', 'Money allocated without a recommended portfolio')
        if comparison.get('choice_changes_without_edge_filter'):
            flag('SENSITIVE_CHOICE', 'warning', 'Weak-link filtering changes the preferred portfolio; explain both choices')
    except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
        flag('INVALID_REPORT', 'error', 'Required structured comparison fields are invalid or missing: ' + str(exc))
    if memo_text:
        # Conservative lexical checks: any occurrence is sent for contextual review, including negations.
        for pattern, code, label in [
            (r'jobs\s+saved|closures?\s+(?:prevented|avoided)|protects?\s+\d+\s+(?:businesses|jobs)', 'CAUSAL_LANGUAGE', 'Potential causal benefit claim'),
            (r'closure\s+probabilit|\d+(?:\.\d+)?%\s+(?:risk|chance)', 'PROBABILITY_LANGUAGE', 'Potential unsupported probability claim'),
            (r'grant\s+(?:is\s+)?approved|funds?\s+(?:have\s+been\s+)?transferred', 'APPROVAL_LANGUAGE', 'Potential grant approval or transfer claim')]:
            if re.search(pattern, memo_text, re.I):
                flag(code, 'warning', label + '; inspect context. Phrase detection is not semantic verification.')
        if comparison.get('decision_scope') == 'simulated_scenario' and not re.search(r'simulat|synthetic', memo_text, re.I):
            flag('MISSING_SIMULATION_LABEL', 'error', 'Memo must label synthetic financial inputs')
    flag('UNVERIFIED_DOCUMENTS', 'warning', 'Provenance labels and evidence notes are supplied; no documents were independently audited')
    flag('MODELED_RELATIONSHIPS', 'warning', 'Supply links are modeled; transaction validation, substitution and causal grant effects remain unknown')
    return {'status': 'blocked' if any(f['severity'] == 'error' for f in findings) else 'review_required',
            'approval_ready': False, 'consistency_checks_passed': not any(f['severity'] == 'error' for f in findings),
            'memo_screened': bool(memo_text), 'findings': findings,
            'evidence_to_collect': ['Documented cash gap and request', 'Operating plan covering the stated horizon',
                                    'Observed supplier/customer links and substitutes', 'Community access, cultural value and equity evidence'],
            'limits': 'Deterministic consistency and conservative phrase checks; not a document audit, semantic proof or approval.'}
