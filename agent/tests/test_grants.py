import asyncio
import pytest
from grant_advisor.decision import allocate, cents, validate
from grant_advisor import tools
from google.adk.tools.function_tool import FunctionTool


def candidate(id, cost, filtered, baseline=None):
    return {'business_id': id, 'gap_cents': cost, 'request_cents': cost,
            'filtered_ids': filtered, 'baseline_ids': baseline or filtered}


def applicant(id='a', **updates):
    return {'business_id': id, 'cash_gap': 50, 'requested_amount': 50,
            'input_type': 'simulated', 'evidence_note': 'Test only, not applicant facts.',
            'operating_assumption': 'Assume full gap funding sustains operation for 30 days.', **updates}


def test_portfolio_deduplicates_overlap_and_excludes_funded_seeds():
    d = allocate(10000, [candidate('a', 5000, ['x', 'b']), candidate('b', 5000, ['x', 'y', 'z'])])
    # Both grants have the same external exposure as b alone; avoid redundant spending.
    assert d['recommendation']['business_ids'] == ['b']
    assert d['recommendation']['filtered_exposure_count'] == 3
    assert d['unallocated_amount'] == 50


def test_combined_portfolio_can_win_without_double_counting():
    d = allocate(10000, [candidate('a', 5000, ['x', 'y']), candidate('b', 5000, ['y', 'z'])])
    assert d['recommendation']['business_ids'] == ['a', 'b']
    assert d['recommendation']['filtered_exposure_count'] == 3
    assert d['recommendation']['amount'] == 100


def test_weak_link_filter_can_change_choice():
    d = allocate(5000, [candidate('a', 5000, ['x'], ['x', 'y', 'z']), candidate('b', 5000, ['y', 'z'])])
    assert d['recommendation']['business_ids'] == ['b']
    assert d['baseline_choice']['business_ids'] == ['a']
    assert d['choice_changes_without_edge_filter'] is True


def test_no_partial_grant_or_zero_evidence_recommendation():
    assert allocate(4999, [candidate('a', 5000, ['x'])])['recommendation'] is None
    assert allocate(5000, [candidate('a', 5000, [])])['recommendation'] is None
    c = candidate('a', 5000, ['x']); c['request_cents'] = 4000
    assert allocate(10000, [c])['feasible_portfolios'] == 0


@pytest.mark.parametrize('value', [0, -1, 'NaN', 'Infinity', 1.001, None, True, '1e100'])
def test_invalid_money(value):
    with pytest.raises(ValueError): cents(value)


def test_cents_and_required_provenance():
    assert cents('0.29') == 29
    with pytest.raises(ValueError): validate(100, [applicant(), applicant()], 30)
    with pytest.raises(ValueError): validate(100, [applicant(), applicant('b', evidence_note=None)], 30)
    with pytest.raises(ValueError): validate(100, [applicant(), applicant('b')], True)


def test_comparison_fails_closed_on_missing_graph(monkeypatch):
    async def unavailable(*args): return {'status': 'unavailable', 'message': 'MCP offline'}
    monkeypatch.setattr(tools, 'analyze_cascade', unavailable)
    d = asyncio.run(tools.compare_applicants(100, [applicant(), applicant('b')], 30))
    assert d['status'] == 'incomplete' and 'recommendation' not in d


def test_comparison_preserves_simulated_scope_and_exact_amounts(monkeypatch):
    async def evidence(id, *args):
        ids = ['x', 'y'] if id == 'a' else ['y']
        return {'status': 'ok', 'seed': {'name': id},
                'baseline': {'exposed_businesses': [{'business_id': i} for i in ids]},
                'filtered': {'exposed_businesses': [{'business_id': i} for i in ids]}}
    monkeypatch.setattr(tools, 'analyze_cascade', evidence)
    d = asyncio.run(tools.compare_applicants(100, [applicant(), applicant('b')], 30))
    assert d['decision_scope'] == 'simulated_scenario'
    assert d['recommendation']['business_ids'] == ['a']
    assert [a['grant_amount'] for a in d['applicants']] == [50, 0]
    assert d['unallocated_amount'] == 50


def test_adk_exposes_comparison_schema():
    declaration = FunctionTool(tools.compare_applicants)._get_declaration()
    schema = declaration.model_dump(exclude_none=True)
    assert schema['name'] == 'compare_applicants'
    assert 'applicants' in schema['parameters_json_schema']['properties']
