from corridor_coordinator.agent import root_agent
import asyncio
from types import SimpleNamespace
from corridor_coordinator.delegation import receipt, EvidenceAgentTool
from google.adk.tools import AgentTool


def test_router_exposes_specialists_without_own_calculator():
    assert root_agent.name == 'corridor_coordinator'
    assert {t.agent.name for t in root_agent.tools} == {
        'cascade_analyst', 'grant_advisor', 'evidence_reviewer', 'neighborhood_context'}
    assert 'ask concisely' in root_agent.instruction.lower()


def test_receipt_preserves_counts_and_failure_status():
    r = receipt('analyze_cascade', {'status':'ok', 'baseline':{'exposed_business_count':23,
        'exposed_businesses':[{'business_id':'x'}]}, 'filtered':{'exposed_business_count':7}})
    assert r['baseline']['exposed_business_count']==23 and r['filtered']['exposed_business_count']==7
    assert 'exposed_businesses' not in r['baseline']
    assert receipt('analyze_cascade',{'status':'unavailable'})['status']=='unavailable'


def test_delegation_prose_and_structured_evidence_are_separate(monkeypatch):
    async def fake(self, *, args, tool_context):
        tool_context.state[self.evidence_key]=[{'tool':'analyze_cascade','status':'unavailable'}]
        return 'Unreliable prose'
    monkeypatch.setattr(AgentTool, 'run_async', fake)
    tool = root_agent.tools[0]
    r=asyncio.run(tool.run_async(args={'request':'test'},tool_context=SimpleNamespace(state={})))
    assert r['status']=='incomplete' and r['tool_evidence'][0]['status']=='unavailable'
