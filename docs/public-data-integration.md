# Public business status and WARN integration

Deployment verified October 20, 2026: Cloud Run `cascade-analyst-00008-wj4` at https://cascade-analyst-89073885580.us-central1.run.app. Both public tables loaded successfully; all 232 existing graph business IDs have registry matches. A live Gemini/MCP query retrieved Steel + Lacquer's exact-ID record (no closure recorded as of October 20) and all 12 county WARN notices. Forty-two local tests passed. The first Cloud Build attempt returned INTERNAL_ERROR; the retry succeeded.

Load jobs: `15a05c66-9ef0-438f-b93b-a459bf612716` (4,571 registry rows) and `d4055e8e-7682-43c6-9a85-c3959344f16c` (12 WARN rows). Remote manifest and tool trace are saved under `public-records-snapshot/manifest.json` and `reports/public-records-deployment.json`.

The loader `scripts/load_public_records.py` fetches official DataSF registry rows for Central Market and the California EDD daily WARN workbook. It loads separate snapshot tables in `a4i_econ`; existing business, supply, footfall and graph data are preserved.

## Sources and scope

- DataSF Registered Business Locations: https://data.sf.gov/resource/g8m3-pdis.json. Snapshot fetched October 20, 2026: 4,571 Central Market records, including historical ownership/location records. Source as-of date: October 20, 2026.
- California EDD WARN workbook: https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx. Retrieved report covers processed records July 1–October 14, 2026. Twelve San Francisco County notices were retained. Records include announced dates, company/address, event type and affected employees.

## Tables

`public_business_status` uses DataSF `uniqueid` as record ID and `ttxid` as the exact location/business ID. It retains name, legal name, address, location start/end dates, DBA end date, administrative status, source as-of/load date, retrieval timestamp and source URL. Multiple records can refer to one graph business: history must not be collapsed into a claim that a business is open or closed.

`public_warn_notices` uses a deterministic content hash as notice ID. It retains county, notice/processed/effective dates, company, event type, affected employee count, address, industry, source row, report title, retrieval timestamp and source URL. No business foreign key is created: San Francisco County is wider than Central Market, and no employer/address match to graph businesses or workplace blocks is verified.

## Agent behavior

- Neighborhood Context exposes `get_public_business_context` through fixed read-only Google MCP Toolbox queries.
- Cascade Analyst can check source status when asked whether a hypothetical closure is real; graph paths remain modeled.
- Grant Advisor includes public records in each applicant comparison without changing the allocation objective.
- Evidence Reviewer flags unavailable, missing, mixed or closed registry records for human checks and preserves unverified WARN linkage.
- Corridor Coordinator routes public closure/layoff questions to Neighborhood Context.

No closure recorded does not verify present operation, financial health or eligibility. WARN effective dates are announced dates, not verified outcomes, and the source excludes many smaller closures. These records do not supply grant applications, cash gaps, actual transactions or proven intervention effects.

## Refresh and verify

Run in an authenticated Cloud Shell with Python 3.11+:

```bash
agent/.venv/bin/pip install openpyxl==3.1.5
agent/.venv/bin/python scripts/load_public_records.py --load --output public-records-snapshot
```

Each refresh replaces only the two public snapshot tables. Raw JSON and the source/load manifest are saved to the ignored snapshot directory. The manifest records source scope, retrieval date, workbook SHA256, load job IDs, row counts and exact overlap with existing business IDs.

From `agent/`, after deploying:

```bash
.venv/bin/python verify_public_records.py https://cascade-analyst-89073885580.us-central1.run.app
```

This requires a successful live Gemini tool call and actual MCP-returned registry and WARN rows. Tool traces are saved under ignored `reports/`. Financial applications remain officer-supplied; no public applicants were fabricated.
