"""Live routing assertions: inspect nested specialist events, not just router prose."""
import argparse
import json
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('url')
args = parser.parse_args()


def request(path, data=None):
    req = urllib.request.Request(args.url.rstrip('/') + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=300) as r: return json.load(r)


scenario = json.loads(Path('grant_advisor/demo.json').read_text())
cases = [
    ('cascade', 'Analyze supply_disruption for Steel + Lacquer, ID 1026779-04-151, at two hops with cutoff 0.01.', {'cascade_analyst'}, {'analyze_cascade'}),
    ('neighborhood', 'Explain worker and neighborhood context for Blick Art Materials, ID 1080659-07-161.', {'neighborhood_context'}, {'get_neighborhood_context'}),
    ('grant', 'Write a grant memo using these explicitly simulated inputs: ' + json.dumps(scenario), {'grant_advisor'}, {'compare_applicants'}),
    ('review', 'Review these explicitly simulated inputs. Pass memo_text unchanged to the reviewer: ' + json.dumps({**scenario, 'memo_text':'SIMULATED. Grant approved. Protects 7 businesses.'}), {'evidence_reviewer'}, {'review_grant_scenario'}),
    ('combined', 'For Steel + Lacquer, ID 1026779-04-151, explain supply_disruption at two hops cutoff 0.01 AND its neighborhood worker context.', {'cascade_analyst','neighborhood_context'}, {'analyze_cascade','get_neighborhood_context'}),
    ('missing', 'Allocate grants. I have not supplied a budget, applicants or financial needs.', set(), set()),
    ('ambiguous', 'Analyze the cascade for Baart Programs Market. Resolve the name and ask which match before tracing if ambiguous.', {'cascade_analyst'}, {'search_businesses'}),
    ('unknown', 'Analyze supply_disruption for exact business ID NOT-IN-CORRIDOR. If missing do not invent any paths.', {'cascade_analyst'}, {'analyze_cascade'}),
]
Path('reports').mkdir(exist_ok=True)
assert 'corridor_coordinator' in request('/list-apps')
for label, prompt, expected_agents, expected_tools in cases:
    session = request('/apps/corridor_coordinator/users/router-check/sessions', {})
    events = request('/run', {'appName':'corridor_coordinator','userId':'router-check','sessionId':session['id'],
        'newMessage':{'role':'user','parts':[{'text':prompt}]}})
    Path(f'reports/router-{label}.json').write_text(json.dumps(events,indent=2))
    parts = [p for e in events for p in (e.get('content') or {}).get('parts', [])]
    calls = {p['functionCall']['name'] for p in parts if 'functionCall' in p}
    responses = [p['functionResponse'] for p in parts if 'functionResponse' in p]
    assert expected_agents <= calls, (label,calls)
    # AgentTool hides nested events; our wrapper exposes structured evidence receipts.
    evidence = [e for r in responses for e in r['response'].get('tool_evidence', [])]
    tool_responses = [{'name': e['tool'], 'response': e} for e in evidence if e['tool'] in expected_tools]
    assert expected_tools <= {r['name'] for r in tool_responses}, (label, responses)
    text = '\n'.join(p['text'] for p in parts if p.get('text') and not p.get('thought'))
    assert text.strip(), label
    if label in ('cascade','neighborhood','grant','review','combined'):
        assert all(r['response'].get('status') in ('ok','review_required') for r in tool_responses), tool_responses
    if label == 'missing': assert not calls, calls
    if label == 'ambiguous': assert 'analyze_cascade' not in {e['tool'] for e in evidence}, evidence
    if label == 'unknown': assert any(r['response'].get('status') == 'not_found' for r in tool_responses)
    print('ROUTER_CASE_PASSED',label,sorted(calls),flush=True)
print('ROUTER_VERIFIED',flush=True)
