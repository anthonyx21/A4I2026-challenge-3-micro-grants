# ReliefIQ — data provenance sheet

Counts below were recorded from the deployed dataset on October 20, 2026. BigQuery location is `US`; dataset is `qwiklabs-gcp-04-029c15637557.a4i_econ`.

| Input | Classification | Source / storage | What it can support | What it cannot establish |
|---|---|---|---|---|
| 232 business locations | Public records | DataSF registry → `businesses` | Identifiers, recorded names, addresses, industry and corridor. | Current financial health, operating status or eligibility. |
| 994 supply links | Modeled | BEA coefficients, industry matching and proximity → `supplies` | Directional network scenarios and threshold-sensitive reach. | Observed transactions, confirmed supplier contracts or causal closure effects. |
| 122 workplace blocks | Public job totals with approximate coordinates | Census LEHD/LODES → `employer_blocks` | Workplace context; coordinates derive from tract internal points. | Employment at a particular applicant or precise block-centroid geometry. |
| 1,024 worker connections | Modeled | Proximity allocation → `draws_footfall_from` | Potential workplace/consumer context. | Measured visits, purchases or revenue. `worker_share` is an allocated worker count. |
| Seven demographic tracts | Public statistical estimates | Census ACS → `tract_demographics` | Population, income, poverty, vehicle access and assistance context. | Individual applicant or customer characteristics. Rates are fractions; estimates have uncertainty. |
| Four historical lending records | Public records with unverified matching | SBA → `borrowed_from` | Historical matched loan context. Recorded rows were `EXEMPT`, `charged_off=false`. | Current cash gaps or verified financial distress. Name matching is not independent verification. |
| 4,571 registry-history rows | Dated public snapshot | [DataSF API](https://data.sf.gov/resource/g8m3-pdis.json) → `public_business_status` | Exact-ID history for all 232 graph business IDs, source dates and recorded end dates. | Proof that a business is currently operating; multiple historical rows must be interpreted together. |
| 12 WARN notices | Dated county public snapshot | [California EDD workbook](https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx) → `public_warn_notices` | San Francisco County notices; processed coverage July 1–October 14, 2026. | Verified links to corridor applicants or workplace blocks. Effective dates are announced dates, not independently confirmed outcomes. |
| Eight applications | Simulated | `frontend/seed_data.json` → PostgreSQL `applications` | Demonstration of review, editing, input snapshots and full-gap allocation. | Factual requests, owners, revenue, staffing, distress or document verification for those real business identities. |
| UI scores and partner illustrations | Simulated | Seed JSON → application/workspace payloads | Demonstration of dashboard layout and review navigation. | Live analytical rankings or observed partner links. |
| Reviewer edits and memo versions | Workflow records | PostgreSQL `reliefiq` | What was entered, analyzed and generated, with versioned snapshots. | Independent validation of the entered information or automatic approval. |

## Linking rules

Applications refer to BigQuery businesses by registry ID, without a cross-database enforced foreign key. Public registry history uses exact business/location IDs. WARN remains county context and deliberately has no applicant foreign key. Employer-block tracts describe workplace context; they are not a direct business-to-tract mapping.

## Dates, refresh and model use

The added public snapshots were retrieved October 20, 2026. Refresh is manual through the existing public loader; the source/load manifest records scope, dates, hashes and row counts. A fresh dataset read does not mean every underlying source observation is current.

The agents retrieve these datasets using tools and reason about their results with Gemini. No model training or fine-tuning on these tables was performed. Supply assumptions and applicant operating assumptions must remain visible in recommendations.

See the [root database diagrams and field dictionary](../../README.md), [analytical ERD](../data-erd.md), and [public-source integration](../public-data-integration.md).
