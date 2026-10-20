# ReliefIQ source coefficients

The committed BEA files support the modeled supply relationships loaded into BigQuery. They describe industry-level requirements, not observed purchases between specific businesses.

| File | Fields and purpose |
|---|---|
| `bea_direct_requirements.csv` | `buyer_naics4`, `supplier_naics4`, `coefficient`: supplying-industry input per dollar of purchasing-industry output. |
| `bea_naics_concordance.csv` | Mapping between BEA industry categories and NAICS used by the coefficient generator. |

The coefficient source is BEA input-output data. Business-level links are constructed from industry matches and proximity; this modeling step does not verify actual supplier relationships. BEA-to-NAICS categories are approximate rather than uniformly one-to-one.

The generator is [scripts/fetch_bea.py](../scripts/fetch_bea.py). The original data-loading notebook is preserved under [archive/starter/notebooks](../archive/starter/notebooks/). Live business, lending, workplace and demographic records reside in BigQuery, rather than this folder. The added public snapshot loader is [scripts/load_public_records.py](../scripts/load_public_records.py).

BEA source terms: [public-domain guidance](https://bea.gov/help/faq/145). Third-party source terms remain applicable; see the repository [NOTICE](../NOTICE).
