# Submission data tools

## Public records loader

`load_public_records.py` fetches official DataSF Central Market registry history and California EDD San Francisco County WARN notices. It refreshes only `public_business_status` and `public_warn_notices` in BigQuery.

```bash
python -m pip install -r agent/requirements.txt openpyxl==3.1.5
python scripts/load_public_records.py --output public-records-snapshot
python scripts/load_public_records.py --load --output public-records-snapshot
```

The first command to the loader saves a snapshot without writing BigQuery. `--load` requires Google credentials. Options include `--project`, `--dataset`, `--corridor`, and `--output`. Defaults target the submission project, `a4i_econ`, and Central Market; WARN remains county context.

The manifest preserves source dates, retrieval time, workbook hash, row counts, load jobs and registry-ID overlap. Refresh is manual. Registry/WARN data does not establish current financial need or grant eligibility. See [public-data integration](../docs/public-data-integration.md).

## BEA coefficient source

`fetch_bea.py` preserves the generator for the committed BEA coefficient and NAICS-concordance files in [data/](../data/). It requires a BEA API key and is not part of runtime agent execution. The original classroom snapshot loader and publisher are retained in [archive/starter](../archive/starter/).
