# ReliefIQ — five-minute demo guide

## Preparation

Open https://reliefiq-backend-89073885580.us-central1.run.app/ and select **Quick Demo Login** (shared demonstration password: `demopassword`). Open **Steel + Lacquer** and confirm a saved memo is available. Keep the [example Word report](ReliefIQ-Example-Grant-Memo.docx) available as a fallback.

For a predictable presentation, use saved reports. New questions invoke live agents; generating a memo saves a new report and can take several minutes. Do not edit inputs or record recommendations during a read-only presentation. Their controls can be shown without saving.

## Presenter walkthrough

| Time | Action | What to explain |
|---|---|---|
| 0:00–0:40 | Show Dashboard and the available pool. | “We help officers inspect relief applications and explain a conditional recommendation.” The seeded pool is $150,000 total, $100,000 committed and $50,000 available; live settings may have changed. |
| 0:40–1:20 | Open Steel + Lacquer; show Application, Documents and Financials. | “These are simulated application inputs linked to a real registry identifier. Document checklists are metadata, not uploaded evidence.” |
| 1:20–2:00 | Show the agent selector and review assistant. | “The coordinator routes questions to four specialists. They retrieve graph, neighborhood and public context through tools.” Use the prompts below if demonstrating live responses. |
| 2:00–3:10 | Open an existing Grant Memo tab. | “The report has seven sections. Its amounts and comparison inputs are saved alongside the evidence.” In the preserved two-applicant example, each $15,000 request is below an $18,000 gap, so no allocation is feasible under full-gap funding. |
| 3:10–4:00 | Show memo versions and Download Word memo. | “Earlier versions retain their original inputs. Saving newer inputs requires a new analysis.” The API reports stale versions; the UI also reminds reviewers that later edits require a new memo. |
| 4:00–5:00 | Show the architecture in the root README and close with limitations. | “PostgreSQL stores applications and reports; BigQuery informs agent analysis. Human reviewers still verify financial need and approve funding.” |

## Sample live questions

Select the relevant specialist for a focused example, or leave **Auto · Corridor Coordinator** selected.

| Agent | Copy/paste prompt | Expected behavior |
|---|---|---|
| Cascade Analyst | `For Steel + Lacquer (1026779-04-151), explain the two-hop supply-disruption cascade at an intensity threshold of 0.01. Distinguish modeled exposure from predicted closures.` | Named modeled paths and cutoff-sensitive counts. Recorded benchmark: 23 unfiltered endpoints, seven filtered; current data may differ. |
| Neighborhood Context | `What do the public registry records say about Steel + Lacquer (1026779-04-151), and how should I interpret the San Francisco County WARN notices? Include source dates and match limits.` | Dated registry information; county WARN context without inventing applicant links. |
| Evidence Reviewer | `What must a reviewer verify before relying on this simulated application and a modeled supply-chain recommendation?` | Financial/document provenance, operating assumptions, missing evidence and limits on causal claims. |
| Grant Advisor | Use **Generate Dashboard Memo**. | Saved database inputs, a shortlist of up to six applicants, live evidence and a versioned report. The default shortlist differs from the two-applicant archived example. |

## What to show if live generation is slow or fails

Open a previously saved report or the example Word file. Say: “This is a report generated during our recorded live verification.” Keep it separate from the pending run. A failed run should show an error and produce no successful memo; it should not be presented as a new successful result.

## Claims to keep precise

- Scores and illustrated network links in the application pane are seeded previews; use saved analytical evidence for live counts.
- Modeled reach is conditional exposure, not actual purchases, jobs saved or proven closures prevented.
- Public records do not establish financial need, current operation or grant eligibility.
- Human recommendations record reviewer intent; they do not approve or pay grants.
- The default agent tool compares six of eight applicants at most.
