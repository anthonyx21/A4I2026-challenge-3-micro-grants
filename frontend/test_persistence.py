import asyncio
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from frontend import persistent_api as api
from frontend.database import Store, runs
from frontend.server import app

@pytest.fixture
def client(tmp_path,monkeypatch):
    database=Store('sqlite:///'+str(tmp_path/'test.db'));database.seed()
    monkeypatch.setattr(api,'_store',database)
    return TestClient(app)

def test_exact_seed_and_idempotence(client):
    seed=json.loads(Path('frontend/seed_data.json').read_text())
    records={a['id']:a for a in client.get('/api/bootstrap').json()['applications']}
    assert len(records)==8
    for original in seed['applications']:
        for key,value in original.items(): assert records[original['id']][key]==value
    a=records['1026779-04-151'];assert a['cash_gap']==18000 and a['ask']==15000
    response=client.patch('/api/applications/'+a['id'],json={'version':1,'ask':18000})
    assert response.status_code==200
    api.store().seed()
    assert api.store().application(a['id'])['ask']==18000
    assert client.patch('/api/applications/'+a['id'],json={'version':1,'ask':20000}).status_code==409
    reopened=Store(str(api.store().engine.url));assert reopened.application(a['id'])['ask']==18000

def test_memo_saves_evidence_versions_and_download(client,monkeypatch):
    async def agent(url,prompt):
        snapshot=json.loads(prompt.split('Saved input snapshot: ',1)[1])
        report={k:snapshot[k] for k in ('budget','horizon_days','applicants')};report['status']='ok'
        return [{'content':{'parts':[{'functionResponse':{'name':'compare_applicants','response':report}}, {'text':'# Grant Memo\nSimulated financial inputs; conditional recommendation.'}]}}]
    monkeypatch.setattr(api,'invoke_agent',agent)
    response=client.post('/api/applications/1026779-04-151/memos',json={})
    assert response.status_code==200,response.text
    row=response.json();memo=client.get('/api/memos/'+row['id']).json()
    assert memo['run']['status']=='complete' and not memo['stale']
    assert memo['run']['input_snapshot']['applicants'][0]['cash_gap']==18000
    assert client.get('/api/memos/'+row['id']+'/download').content[:2]==b'PK'
    client.patch('/api/applications/1026779-04-151',json={'version':1,'cash_gap':20000})
    assert client.get('/api/memos/'+row['id']).json()['stale']
    assert len(client.get('/api/applications/1026779-04-151/memos').json())==1

def test_wrong_agent_inputs_fail_without_memo(client,monkeypatch):
    async def wrong(url,prompt):
        snapshot=json.loads(prompt.split('Saved input snapshot: ',1)[1]);snapshot['applicants'][0]['cash_gap']=1
        report={k:snapshot[k] for k in ('budget','horizon_days','applicants')};report['status']='ok'
        return [{'content':{'parts':[{'functionResponse':{'name':'compare_applicants','response':report}}, {'text':'Wrong memo'}]}}]
    monkeypatch.setattr(api,'invoke_agent',wrong)
    response=client.post('/api/applications/1026779-04-151/memos',json={})
    assert response.status_code==502
    run=client.get('/api/analysis-runs/'+response.json()['detail']['run_id']).json()
    assert run['status']=='failed'
    assert client.get('/api/bootstrap').json()['memos']==[]

def test_recommendation_budget_enforced(client):
    applications=client.get('/api/bootstrap').json()['applications']
    accepted=0
    for a in applications:
        response=client.post('/api/applications/'+a['id']+'/recommendation',json={'recommended':True})
        if response.status_code==200:accepted+=a['ask']
        else:assert response.status_code==409
    assert accepted<=50000
    assert sum(client.get('/api/bootstrap').json()['recommendations'].values())==accepted

def test_reviewer_authentication(client,monkeypatch):
    monkeypatch.setenv('REQUIRE_REVIEWER_LOGIN','true')
    monkeypatch.setenv('REVIEWER_PASSWORD','test-password')
    assert client.get('/api/bootstrap').status_code==401
    assert client.post('/api/login',json={'password':'wrong'}).status_code==401
    assert client.post('/api/login',json={'password':'test-password'}).status_code==200
    assert client.get('/api/bootstrap').status_code==200

def test_job_claim_prevents_duplicate_execution(client):
    run_id=api.store().create_run('1026779-04-151',{'applications':[]})
    assert api.store().claim_run(run_id)
    assert not api.store().claim_run(run_id)

def test_budget_changes_respect_pool(client):
    assert client.patch('/api/funding-rounds/default',json={'round_budget':60000}).status_code==409
    assert client.patch('/api/funding-rounds/default',json={'round_budget':40000}).status_code==200
    assert client.get('/api/bootstrap').json()['settings']['round_budget']==40000

def test_repeated_click_reuses_active_snapshot(client):
    snapshot={'application_versions':{'1026779-04-151':1}}
    first=api.store().create_run('1026779-04-151',snapshot)
    assert api.store().create_run('1026779-04-151',snapshot)==first
    api.store().fail(first,'offline')
    assert api.store().create_run('1026779-04-151',snapshot)!=first

def test_internal_worker_requires_task_auth(client):
    run_id=api.store().create_run('1026779-04-151',{})
    assert client.post('/api/internal/memo-runs/'+run_id,json={}).status_code==401

def test_interrupted_job_recovers_as_failure(client):
    from sqlalchemy import update
    id=api.store().create_run('1026779-04-151',{})
    with api.store().engine.begin() as connection:
        connection.execute(update(runs).where(runs.c.id==id).values(created_at='2020-01-01T00:00:00+00:00'))
    assert client.get('/api/analysis-runs/'+id).json()['status']=='failed'

def test_note_route_updates_same_application(client):
    response=client.post('/api/applications/1026779-04-151/notes',json={'version':1,'text':'Verify landlord evidence'})
    assert response.status_code==200
    assert client.get('/api/applications/1026779-04-151').json()['notes']['reviewer']=='Verify landlord evidence'
