# ReliefIQ — limitations and next steps

These are documented boundaries and proposed improvements. No implementation changes were made as part of this documentation pack.

| Current boundary | Implication | Proposed next step |
|---|---|---|
| Application inputs are simulated; document records are metadata. | The demonstration cannot establish actual business distress or verified grant requests. | Add consented applications, secure document uploads, provenance review and document access controls. |
| Shared demo reviewer account and public challenge agent endpoint. | The build lacks individual reviewer accountability and production service authentication. | Add organizational identity, roles, per-user audit records, service identity and appropriate access restrictions. |
| Default comparison includes at most six of eight applications. | Results are shortlist decisions, not an all-applicant allocation. | Make shortlist selection explicit; design a validated allocation method for larger pools. |
| Objective favors unique modeled network exposure under full-gap funding. | It omits cultural value, equity policy, replacement suppliers and calibrated causal benefits. | Agree on policy objectives with reviewers, add justified constraints and evaluate sensitivity against alternatives. |
| Supply/footfall links use industry and proximity models. | Named links can be implausible; exposure is not proof of actual commercial dependence. | Validate relationships with consented evidence, explain uncertain links and measure model performance. |
| Registry/WARN snapshots are dated and manually refreshed. | No closure recorded is not current-operation proof; county notices cannot be assigned to applicants. | Add monitored refresh, visible source-age indicators and verified linkage where appropriate. |
| Generated prose is not a fully validated structured report. | A memo may omit GQL, numeric weights or neighborhood details despite having seven headings. | Enforce a report schema, render required evidence directly, and review wording before officer use. |
| ADK chat sessions are process-local. | A restart can reset chat context even though applications and memos persist. | Add durable sessions and retention/access policies. |
| Queue uses one concurrent dispatch and explicit retry after failure. | Long runs can delay other reports; interrupted jobs are recovered when status is checked. | Test expected workloads, improve retry/lease recovery and add operational monitoring. |
| Existing demo timestamps and some notes are stored in JSON/string fields. | Schema flexibility is convenient, but stronger validation and auditing are needed at production scale. | Introduce typed migrations, validated domain fields and append-only audit history as required. |
| Human recommendations do not approve or disburse grants. | The UI demonstrates decision support, not a funding transaction system. | Integrate a controlled approval workflow only after policy, identity and audit requirements are defined. |
| Qwiklabs infrastructure has a limited lifetime. | Submission links may expire with the project. | Preserve example reports and evidence; move to a funded project for continued operation. |

## Suggested priorities after the challenge

1. Validate real applicant evidence and implement individual reviewer identity.
2. Establish the allocation and equity policy with intended users.
3. Make report rendering complete and evidence-driven, with human review.
4. Evaluate model quality, operational reliability and costs before a larger pilot.

We have demonstrated persistent application review and tool-supported conditional memos. We have not measured reduced closures, jobs saved, fairness outcomes or real-world grant impact.
