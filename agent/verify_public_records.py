"""Authenticated deployment check requiring live public-record MCP evidence."""
import argparse,json,subprocess,urllib.request
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('url');a=p.parse_args()
token=subprocess.check_output(['gcloud','auth','print-identity-token'],text=True).strip()
def request(path,data=None):
 r=urllib.request.Request(a.url.rstrip('/')+path,data=json.dumps(data).encode() if data is not None else None,
                         headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
 with urllib.request.urlopen(r,timeout=300) as response:return json.load(response)
assert 'neighborhood_context' in request('/list-apps')
s=request('/apps/neighborhood_context/users/public-check/sessions',{})
events=request('/run',{'appName':'neighborhood_context','userId':'public-check','sessionId':s['id'],
 'newMessage':{'role':'user','parts':[{'text':'Use get_public_business_context for business ID 1026779-04-151. Report dated registry status and separately describe SF County WARN scope. Do not claim WARN employers match this business.'}]}})
responses=[p['functionResponse'] for e in events for p in (e.get('content') or {}).get('parts',[]) if 'functionResponse' in p]
r=next((r['response'] for r in responses if r['name']=='get_public_business_context'),None)
assert r and r['status']=='ok',responses
assert r['registry_source_as_of'] and r['registry_records'] and r['warn_notice_count']>0,r
assert all(x['business_id']=='1026779-04-151' for x in r['registry_records'])
Path('reports').mkdir(exist_ok=True)
Path('reports/public-records-deployment.json').write_text(json.dumps(events,indent=2))
print('PUBLIC_RECORDS_VERIFIED',r['business_id'],r['registry_status'],r['registry_source_as_of'],len(r['registry_records']),r['warn_notice_count'])
for e in events:
 for part in (e.get('content') or {}).get('parts',[]):
  if part.get('text') and not part.get('thought'):print(part['text'])
