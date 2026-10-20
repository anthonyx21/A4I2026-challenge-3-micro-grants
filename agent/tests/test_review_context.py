from copy import deepcopy
import pytest
from evidence_reviewer.review import audit_comparison
from neighborhood_context.tools import summarize_context
from google.adk.tools.function_tool import FunctionTool
from evidence_reviewer.tools import review_grant_scenario
from neighborhood_context.tools import get_neighborhood_context


def report():
    a = {'business_id': 'a', 'input_type': 'simulated', 'cash_gap': 50, 'requested_amount': 50,
         'grant_amount': 50, 'evidence_note': 'Demo only', 'operating_assumption': '30 days',
         'cascade': {'status': 'ok', 'filtered': {'exposed_business_count': 1,
                    'exposed_businesses': [{'business_id': 'x'}]}}}
    return {'status': 'ok', 'decision_scope': 'simulated_scenario', 'budget': 100,
            'unallocated_amount': 50, 'applicants': [a], 'choice_changes_without_edge_filter': True,
            'recommendation': {'business_ids': ['a'], 'amount': 50,
                               'filtered_exposure_count': 1, 'filtered_exposed_ids': ['x']}}


def test_consistency_pass_is_never_approval():
    r = audit_comparison(report(), 'Simulated scenario with modeled exposure.')
    assert r['status'] == 'review_required' and r['consistency_checks_passed']
    assert r['approval_ready'] is False
    assert {'SIMULATED_INPUTS', 'SENSITIVE_CHOICE', 'UNVERIFIED_DOCUMENTS'} <= {f['code'] for f in r['findings']}


@pytest.mark.parametrize('field,value,code', [
    ('unallocated_amount', 40, 'BUDGET_RECONCILIATION'),
    ('budget', 20, 'BUDGET_EXCEEDED'),
    ('decision_scope', 'conditional_decision_support', 'PROVENANCE_MISMATCH')])
def test_review_blocks_inconsistent_report(field, value, code):
    d=report(); d[field]=value
    r=audit_comparison(d)
    assert r['status']=='blocked' and code in {f['code'] for f in r['findings']}


def test_review_checks_portfolio_identity_union():
    d=report(); d['recommendation']['filtered_exposed_ids']=['invented']
    assert 'PORTFOLIO_COUNT_MISMATCH' in {f['code'] for f in audit_comparison(d)['findings']}


def test_memo_flags_are_conservative_and_label_missing_simulation():
    r=audit_comparison(report(), 'This protects 7 businesses and saves jobs. Grant approved.')
    assert {'CAUSAL_LANGUAGE', 'APPROVAL_LANGUAGE', 'MISSING_SIMULATION_LABEL'} <= {f['code'] for f in r['findings']}
    r=audit_comparison(report(), 'Simulated. Do not claim jobs saved.')
    assert 'CAUSAL_LANGUAGE' in {f['code'] for f in r['findings']}


def test_review_fails_closed_for_missing_fields_or_outage():
    assert audit_comparison({'status':'unavailable'})['status']=='blocked'
    assert audit_comparison({'status':'ok'})['status']=='blocked'


def context():
    return ({'business_id':'a'}, [{'tract_id':'06075012301','edge_count':2,'block_count':2,
             'modeled_worker_allocation':0.25,'linked_block_jobs':20}],
            [{'tract_id':'06075012301','total_pop':100,'median_income':10000,
              'poverty_rate':0.2,'no_vehicle_rate':0.5,'assistance_rate':None}])


def test_worker_allocations_remain_fractional_and_distinct_from_jobs():
    r=summarize_context(*context())
    assert r['modeled_worker_allocation']==0.25 and r['linked_block_jobs']==20
    assert r['linked_tracts'][0]['demographics']['poverty_rate']==0.2
    assert 'poverty_rate' not in r  # No invented corridor aggregate.


def test_no_links_and_missing_demographics_are_explicit():
    seed,rows,demographics=context()
    assert summarize_context(seed,[],demographics)['footfall_status']=='no_modeled_links'
    r=summarize_context(seed,rows,[])
    assert r['missing_demographic_tracts']==['06075012301']
    assert r['linked_tracts'][0]['demographics'] is None


def test_rejects_inflation_bad_rate_and_truncation():
    seed,rows,demographics=context()
    dup=deepcopy(rows);dup[0]['edge_count']=3
    with pytest.raises(ValueError):summarize_context(seed,dup,demographics)
    bad=deepcopy(demographics);bad[0]['poverty_rate']=20
    with pytest.raises(ValueError):summarize_context(seed,rows,bad)
    with pytest.raises(ValueError):summarize_context(seed,rows,demographics*501)


def test_new_adk_schemas_and_grant_specialists_import():
    from grant_advisor.agent import root_agent
    assert {'evidence_reviewer','neighborhood_context'} <= {t.agent.name for t in root_agent.tools if hasattr(t,'agent')}
    assert FunctionTool(review_grant_scenario)._get_declaration().name=='review_grant_scenario'
    assert FunctionTool(get_neighborhood_context)._get_declaration().name=='get_neighborhood_context'
