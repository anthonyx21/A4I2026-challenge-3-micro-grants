# ReliefIQ — submission summary

**Agents for Impact 2026 · Challenge 3: Community Economic Resilience & Micro-Grants · Track 1: Main Street Relief**

## Real-world challenge

Small-business closures can disrupt suppliers, workers and nearby businesses. Grant reviewers need to decide where scarce relief funds can help while explaining the evidence, assumptions and tradeoffs behind each recommendation.

## Who benefits

Small businesses, corridor workers and residents benefit from more informed relief decisions. Reviewers gain a shared workspace for inspecting applications and producing an auditable case for human approval.

## Our solution

ReliefIQ combines a grant-review dashboard with five ADK agents: Corridor Coordinator, Grant Advisor, Cascade Analyst, Neighborhood Context and Evidence Reviewer. Officers review saved application inputs, ask questions, and request a conditional grant memo supported by live analytical tools.

The backend stores application edits, budgets, reviewer notes, recommendations and memo versions in PostgreSQL. Each memo retains its input snapshot and structured comparison evidence; reports reopen after refresh and export to Word.

## Data ecosystem

The demonstration uses eight simulated applications attached to actual San Francisco registry identifiers. BigQuery supplies 232 business locations, 994 modeled supply links, 122 workplace blocks, 1,024 modeled worker connections, seven demographic tracts and four matched historical SBA records. Added public snapshots contain 4,571 registry-history rows and 12 San Francisco County WARN notices, recorded October 20, 2026.

Registry identities and public records are sourced; business supply/footfall links are modeled; application financials, owners and document claims are simulated. The agent retrieves and analyzes these inputs; we did not train or fine-tune a model on them.

## Technical build

Google Cloud Run hosts the dashboard/backend and five-agent service. Cloud SQL PostgreSQL stores workflow state; Cloud Tasks queues memo generation; Secret Manager supplies backend credentials. Vertex AI Gemini 2.5 Flash powers agent reasoning. Embedded Google MCP Toolbox provides fixed read-only BigQuery queries. Word export is implemented in the backend, rather than a separate MCP report service.

## Demonstrated outcomes

Recorded verification covers persistent edits, queued live memo generation, matching saved input/evidence snapshots, saved report versions and Word downloads. Fourteen backend/chat tests passed during implementation. These demonstrate decision-support behavior, not proven business survival or job-saving outcomes.

## Try it

**Dashboard:** https://reliefiq-backend-89073885580.us-central1.run.app/  
**Agent service:** https://cascade-analyst-89073885580.us-central1.run.app/  
**Project:** `qwiklabs-gcp-04-029c15637557`

Select **Quick Demo Login**, open an application, then review a saved memo or select **Generate Dashboard Memo**. The default comparison includes up to six applications, not all eight. Recommendations require human review and do not disburse funds. Availability depends on the Qwiklabs project lifetime.
