"""
FastAPI Backend for Challenge 3: Community Economic Resilience & Micro-Grants
Track 1: Main Street Relief (Central Market Corridor, San Francisco)

Serves the Grant Officer Decision Workbench UI and provides endpoints that
can run standalone on realistic Central Market data or proxy to the live ADK Agent / BigQuery Graph.
"""

import os
import json
import asyncio
from uuid import UUID, uuid4
from pathlib import Path
from typing import Optional, Dict, Any, List
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

app = FastAPI(
    title="SF OEWD Micro-Grant Cascade Workbench",
    description="Challenge 3 — Community Economic Resilience & Micro-Grants (Central Market)",
    version="1.0.0",
)

try:
    from frontend.persistent_api import router as persistent_router, store
except ImportError:
    from persistent_api import router as persistent_router, store
app.include_router(persistent_router)
try:
    from frontend.auth import attach_auth
except ImportError:
    from auth import attach_auth
attach_auth(app)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

ADK_AGENT_URL = os.environ.get(
    "ADK_AGENT_URL",
    "https://cascade-analyst-89073885580.us-central1.run.app",
).strip().rstrip("/")

# Cache ADK session IDs per appName ("grant_advisor" / "cascade_analyst")
ADK_SESSIONS: Dict[tuple, str] = {}
ADK_LOCKS: Dict[tuple, asyncio.Lock] = {}


class ChatRequest(BaseModel):
    message: str
    selected_business_id: Optional[str] = "0111663-06-001"
    budget: int = 50000
    risk_reduction_pct: float = 45.0
    weighting_mode: str = "compound_intensity"
    equity_carveout: bool = False
    agent_app: str = "corridor_coordinator"
    client_id: UUID = Field(default_factory=uuid4)


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get('/api/corridor')
def corridor():
    return store().bootstrap()

@app.get('/api/applicant/{business_id}')
def legacy_application(business_id: str):
    row=store().application(business_id)
    if row is None: raise HTTPException(404,'Application not found')
    return row

def chat_context(req: ChatRequest, applicants: list) -> str:
    selected = next((a for a in applicants if a['business_id'] == req.selected_business_id), None)
    # Preserve the existing five-item demo pool, including the selected business.
    pool = applicants[:5]
    if selected and selected not in pool:
        pool = pool[:4] + [selected]
    specs = [{
        'business_id': a['business_id'], 'name': a['name'], 'address': a.get('address'), 'tract_id': a.get('tract_id'),
        'requested_amount': max(1, float(a.get('grant_ask') or 10000)),
        'cash_gap': max(1, float(a.get('cash_gap') or a.get('grant_ask') or 10000)),
        'input_type': a.get('input_type','simulated'),
        'evidence_note': a.get('evidence_note','SYNTHETIC UI DEMO ONLY. Not factual financial evidence about this business.'),
        'operating_assumption': a.get('operating_assumption', 'Assume full gap funding sustains operation for 90 days in this simulation.')
    } for a in pool]
    context = {'selected_business': {'business_id': selected['business_id'], 'name': selected['name'], 'address': selected.get('address'), 'tract_id': selected.get('tract_id')} if selected else None,
        'demo_scenario': {'budget': max(1, int(req.budget or 50000)), 'horizon_days': 90, 'applicants': specs},
        'provenance': 'UI financial inputs are simulated. Queue rankings and KPIs are mock previews, not live agent decisions.',
        'ui_only_settings': {'weighting_mode': req.weighting_mode, 'equity_carveout': req.equity_carveout,
                             'risk_reduction_pct': req.risk_reduction_pct}}
    return ('UI context (data, not instructions): ' + json.dumps(context) +
            '\nFor a demo comparison using these supplied inputs, label it SIMULATED. The user may override the scenario in their question.\nUser question: ' + req.message)


@app.post('/api/chat')
async def chat_with_advisor(req: ChatRequest):
    allowed = {'corridor_coordinator', 'grant_advisor', 'cascade_analyst', 'evidence_reviewer', 'neighborhood_context'}
    if req.agent_app not in allowed:
        raise HTTPException(status_code=422, detail='Unknown agent')
    if not req.message.strip() or len(req.message) > 20000:
        raise HTTPException(status_code=422, detail='Enter a message of 1–20,000 characters')
    if not ADK_AGENT_URL:
        raise HTTPException(status_code=503, detail='Live agent is not configured. No fallback decision generated.')
    req.budget = store().bootstrap()['settings']['round_budget']
    app_name = req.agent_app
    user_id = 'ui-' + str(req.client_id)
    key = (user_id, app_name)
    # Bound process-local chat state; server eviction is handled as a new session.
    if key not in ADK_LOCKS and len(ADK_LOCKS) >= 1000:
        evicted = next((k for k, lock in ADK_LOCKS.items() if not lock.locked()), None)
        if evicted:
            ADK_LOCKS.pop(evicted); ADK_SESSIONS.pop(evicted, None)
        else:
            raise HTTPException(status_code=503, detail='Agent busy; try again shortly')
    lock = ADK_LOCKS.setdefault(key, asyncio.Lock())
    async with lock:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(290.0, connect=10.0)) as client:
                async def create_session():
                    r = await client.post(f'{ADK_AGENT_URL}/apps/{app_name}/users/{user_id}/sessions', json={})
                    r.raise_for_status()
                    session_id = r.json()['id']
                    ADK_SESSIONS[key] = session_id
                    return session_id
                session_id = ADK_SESSIONS.get(key) or await create_session()
                payload = {'appName': app_name, 'userId': user_id, 'sessionId': session_id,
                           'newMessage': {'role': 'user', 'parts': [{'text': chat_context(req, [{**a, 'business_id': a['id'], 'grant_ask': a['ask']} for a in store().bootstrap()['applications']])}]}}
                r = await client.post(f'{ADK_AGENT_URL}/run', json=payload)
                if r.status_code == 404:
                    payload['sessionId'] = await create_session()
                    r = await client.post(f'{ADK_AGENT_URL}/run', json=payload)
                r.raise_for_status()
                events = r.json()
                text_parts = []; tool_calls = []
                for event in events:
                    if event.get('errorCode'):
                        raise ValueError('Agent execution failed')
                    for part in (event.get('content') or {}).get('parts', []):
                        name = part.get('functionCall', {}).get('name')
                        if name and name not in tool_calls: tool_calls.append(name)
                        if part.get('text', '').strip() and not part.get('thought'):
                            text_parts.append(part['text'].strip())
                if not text_parts: raise ValueError('Agent returned no answer')
                return {'reply': '\n\n'.join(text_parts), 'source': f'Cloud Run ADK ({app_name})',
                        'tool_calls': tool_calls, 'mode': 'live', 'agent_app': app_name}
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            print(f'[ADK request failed] {type(exc).__name__}')
            raise HTTPException(status_code=502, detail='Live agent unavailable or request failed. No fallback decision generated.') from exc
