"""Expose bounded tool evidence alongside AgentTool prose for routing auditability."""
from google.adk.tools import AgentTool


def receipt(name, response):
    data = {'tool': name, 'status': response.get('status')}
    for key in ('message', 'decision_scope', 'budget', 'horizon_days', 'direction', 'depth',
                'sensitivity', 'recommendation', 'runner_up', 'unallocated_amount',
                'choice_changes_without_edge_filter', 'approval_ready', 'consistency_checks_passed',
                'findings', 'modeled_worker_allocation', 'linked_block_count', 'linked_block_jobs',
                'missing_demographic_tracts', 'footfall_status', 'seed'):
        if key in response: data[key] = response[key]
    for key in ('baseline', 'filtered'):
        if key in response:
            data[key] = {k:v for k,v in response[key].items() if k != 'exposed_businesses'}
    if 'matches' in response: data['matches'] = response['matches']
    if 'evidence_review' in response: data['evidence_review'] = response['evidence_review']
    return data


class EvidenceAgentTool(AgentTool):
    def __init__(self, agent):
        specialist = agent.model_copy(deep=True)
        key = 'coordinator_evidence_' + agent.name
        async def record(tool, args, tool_context, tool_response):
            if isinstance(tool_response, dict):
                tool_context.state[key] = [*tool_context.state.get(key, []),
                                           receipt(tool.name, tool_response)][-12:]
        specialist.after_tool_callback = record
        super().__init__(agent=specialist)
        self.evidence_key = key

    async def run_async(self, *, args, tool_context):
        tool_context.state[self.evidence_key] = []
        result = await super().run_async(args=args, tool_context=tool_context)
        evidence = tool_context.state.get(self.evidence_key, [])
        failure = any(e.get('status') in ('unavailable', 'incomplete', 'blocked') for e in evidence)
        return {'status': 'incomplete' if failure else 'completed',
                'result': result, 'tool_evidence': evidence,
                'limits': 'Structured receipts are authoritative for counts/status; prose is a specialist explanation.'}
