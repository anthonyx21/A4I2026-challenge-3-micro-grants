# ReliefIQ — two-minute presentation and demo

**Challenge:** Community Economic Resilience & Micro-Grants · Main Street Relief  
**Audience:** Challenge judges and grant reviewers  
**Format:** One presenter, dashboard walkthrough, saved agent report. Start the timer after logging in.

## Prepare before presenting

1. Open [ReliefIQ](https://reliefiq-backend-89073885580.us-central1.run.app/) and select **Quick Demo Login (Reviewer 1)**. Leave the Dashboard visible; confirm it loads and the available budget is visible.
2. In a second tab, open **Steel + Lacquer**. Locate an existing **Grant Memo** in the report pane and its **Download Word memo** link. Check the report's applicant shortlist, amounts and conclusion before speaking about it.
3. Open the preserved [two-applicant example](example-grant-memo.md) and [Word report](ReliefIQ-Example-Grant-Memo.docx) as a fallback. The specific $15,000/$18,000 example in this script refers to that preserved report; it is not the dashboard's default six-applicant comparison.
4. If a fresh report is wanted, select **Generate Dashboard Memo** during preparation and wait for completion. Generation can take several minutes. Use a completed report during the timed demo.
5. Enlarge the browser text so judges can read it. Close unrelated tabs and notifications. Rehearse once with a timer; aim for a steady pace of about 130 words per minute.

## Timed script

Read only the quoted narration aloud. Actions are presenter instructions. The narration is approximately 230 words, leaving time for clicks and transitions.

### 0:00–0:20 — The problem

**Show:** Dashboard, application queue and available funds.

> “We're ReliefIQ. When a small business closes, the effects can spread to suppliers, workers and neighboring businesses. Our Main Street Relief solution helps grant reviewers decide how to use limited funds and explain the evidence behind their choices.”

### 0:20–0:40 — The reviewer workspace

**Do:** Open **Steel + Lacquer**. Click **Application**, then **Financials**. Point to the request and financial inputs.

> “A reviewer opens an application, checks its funding request and financials, and reviews missing information. These demonstration applications are simulated and linked to real business registry identifiers. Edits and reviewer notes are saved in our database.”

### 0:40–1:05 — The agents

**Show:** The review assistant and agent selector. Point to **Generate Dashboard Memo** without starting a new run.

> “Five agents support the review. A coordinator routes questions; the Cascade Analyst explores modeled business dependencies; Neighborhood Context adds local and public records; the Grant Advisor compares funding options; and the Evidence Reviewer checks assumptions. They use ADK and MCP tools to retrieve BigQuery evidence.”

### 1:05–1:35 — The decision and evidence

**Do:** Switch to the prepared report. For this exact narration, show the preserved **two-applicant example**, including its funding conclusion and named cascade paths. Identify it as previously generated.

> “Here is a previously generated two-applicant report. Each business requested fifteen thousand dollars against an eighteen-thousand-dollar gap. Under the full-gap funding assumption, neither qualifies for an allocation. The agents explain that result, show named modeled cascade paths, and separate public records from simulated financials. That gives reviewers a reason to request better evidence instead of forcing a recommendation.”

### 1:35–2:00 — The outcome

**Do:** Return to the prepared dashboard report and show **Download Word memo**; open the downloaded file if ready. Otherwise show the preserved Word example. Finish on the report.

> “Each dashboard memo keeps its original inputs and evidence, can be reopened, and exports to Word. Reviewers gain a documented basis for discussing relief decisions. People still verify need and approve funding. Our goal is more informed support for businesses and communities; this demo demonstrates the workflow, not proven jobs saved.”

## If the demo gets interrupted

- **The app is unavailable:** Use the example memo and Word report. Say, “I'm showing a preserved report from our live verification.” Continue with the agent explanation and report conclusion.
- **Generation is still running:** Show a completed report and identify it as previously generated. Do not wait for the pending run during the presentation.
- **A different saved report is displayed:** Describe its actual shortlist and conclusion. Use the preserved example for the specific two-applicant funding mismatch.
- **You are behind schedule:** Skip the Word download; point to the export link and deliver the closing narration.

## Keep the demonstration accurate

Do not present leaderboard scores or illustrated links as measured impact. Business dependencies are modeled; application financials and document claims are simulated. Public records provide dated context, not proof of eligibility. The default comparison covers up to six applicants, and recording a recommendation does not approve or pay a grant. Avoid saving edits or recommendations during the presentation because they change the shared workspace.
