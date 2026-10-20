"""Authenticated live Grant Advisor check using explicitly simulated financial inputs."""
import argparse
import json
import subprocess
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('url')
args = parser.parse_args()
token = subprocess.check_output(['gcloud', 'auth', 'print-identity-token'], text=True).strip()


def request(path, data=None):
    req = urllib.request.Request(args.url.rstrip('/') + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=300) as response:
        return json.load(response)


health = request('/api/health')
assert health['status'] == 'ok', health
assert {'cascade_analyst', 'grant_advisor'} <= set(request('/list-apps'))
session = request('/apps/grant_advisor/users/grant-check/sessions', {})
scenario = json.loads(Path('grant_advisor/demo.json').read_text())
prompt = ('Produce a grant memo for this explicitly SIMULATED scenario. I authorize using these '
          'synthetic assumptions for the demo; they are not facts about named businesses. '
          'Call compare_applicants with these exact inputs: ' + json.dumps(scenario))
events = request('/run', {'appName': 'grant_advisor', 'userId': 'grant-check',
    'sessionId': session['id'], 'newMessage': {'role': 'user', 'parts': [{'text': prompt}]}})
responses = [p['functionResponse'] for e in events for p in (e.get('content') or {}).get('parts', [])
             if 'functionResponse' in p]
report = next((r['response'] for r in responses if r['name'] == 'compare_applicants'), None)
assert report and report['status'] == 'ok', responses
assert report['decision_scope'] == 'simulated_scenario'
assert len(report['applicants']) == 2
assert all(a['cascade']['status'] == 'ok' for a in report['applicants'])
choice = report['recommendation']
assert choice and choice['amount'] <= scenario['budget'], report
assert sum(a['grant_amount'] for a in report['applicants']) == choice['amount']
memo = '\n'.join(p['text'] for e in events for p in (e.get('content') or {}).get('parts', []) if p.get('text'))
assert 'simulat' in memo.lower() and memo.strip(), memo
Path('reports').mkdir(exist_ok=True)
Path('reports/grant-deployment-verification.json').write_text(json.dumps(events, indent=2))
Path('reports/grant-memo.txt').write_text(memo)
print('HEALTH', health)
for a in report['applicants']:
    print('APPLICANT', a['name'], 'BASELINE', a['cascade']['baseline']['exposed_business_count'],
          'FILTERED', a['cascade']['filtered']['exposed_business_count'], 'GRANT_USD', a['grant_amount'])
print('GRANT_ADVISOR_VERIFIED', choice['business_ids'], 'USD', choice['amount'],
      'EXPOSED', choice['filtered_exposure_count'], 'SENSITIVITY_CHANGES_CHOICE', report['choice_changes_without_edge_filter'])
print(memo)
