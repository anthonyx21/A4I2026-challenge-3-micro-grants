import asyncio
from uuid import uuid4
import httpx
import pytest
from fastapi import HTTPException
from frontend import server


def test_ui_context_preserves_selected_applicant_and_labels_demo():
    req = server.ChatRequest(message='Compare this applicant', selected_business_id=server.store().bootstrap()['applications'][-1]['id'])
    text = server.chat_context(req, [{**a,'business_id':a['id'],'grant_ask':a['ask']} for a in server.store().bootstrap()['applications']])
    assert req.selected_business_id in text
    assert '"input_type": "verified"' not in text
    assert '"input_type": "simulated"' in text
    assert 'mock previews' in text
    assert req.agent_app == 'corridor_coordinator'


def test_frontend_chat_routes_and_isolates_sessions(monkeypatch):
    calls = []
    class Client:
        def __init__(self, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, json):
            calls.append((url, json))
            response = {'id': str(uuid4())} if url.endswith('/sessions') else [
                {'content': {'parts': [{'functionCall': {'name': 'neighborhood_context'}}, {'text': 'Context answer'}]}}]
            return httpx.Response(200, json=response, request=httpx.Request('POST', url))
    monkeypatch.setattr(server.httpx, 'AsyncClient', Client)
    server.ADK_SESSIONS.clear(); server.ADK_LOCKS.clear()
    async def run():
        first = server.ChatRequest(message='Neighborhood context')
        second = server.ChatRequest(message='Neighborhood context')
        for req in (first, first, second):
            r = await server.chat_with_advisor(req)
            assert r['mode'] == 'live' and r['agent_app'] == 'corridor_coordinator'
        return first, second
    first, second = asyncio.run(run())
    sessions = [url for url, data in calls if url.endswith('/sessions')]
    assert len(sessions) == 2 and sessions[0] != sessions[1]
    assert all(data['appName'] == 'corridor_coordinator' for url, data in calls if url.endswith('/run'))


def test_failed_agent_never_returns_mock_graph_answer(monkeypatch):
    class Offline:
        def __init__(self, **kw): pass
        async def __aenter__(self): raise httpx.ConnectError('offline')
        async def __aexit__(self, *args): pass
    monkeypatch.setattr(server.httpx, 'AsyncClient', Offline)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(server.chat_with_advisor(server.ChatRequest(message='Write a memo')))
    assert exc.value.status_code == 502 and 'No fallback' in exc.value.detail
