# Data Contract: Sell-in Sales (v1.2)

Status: v1.2, 2026-10-25


Producer: synthetic generator (`src/`), later replaced by the real sell-in extract
Consumer: demandfcst processing pipeline

Any dataset delivered to the landing area **must** follow this contract,
synthetic or real. The pipeline validates it on arrival and rejects data that breaks a rule.

## 1. General file rules
- Format: CSV, comma separator, header row, `.` as decimal point.
- Encoding: UTF-8 **without BOM**.
- Dates: ISO `YYYY-MM-DD`. Weeks run **Monday to Sunday** and are labelled by their **Monday** (`week_start`).
- Codes (`province`, `sku_id`) are **text**, never numbers.
- Column names: lowercase snake_case; units in the name where relevant.

## 2. Datasets

### 2.1 `sellin_daily` (landing, raw)
One row per province x SKU x day **with sales**. A missing row means zero sales.

| Column | Type | Rules | Example |
|---|---|---|---|
| `date` | date | ISO; within the drop's date range | 2024-01-15 |
| `province` | text | 2-letter state code, uppercase, in `province_master` | SP |
| `sku_id` | text | in `sku_master` | 38958 |
| `volume_hl` | float | > 0, up to 3 decimals, hectolitres | 12.450 |

Primary key: (`province`, `sku_id`, `date`), with no duplicates.

### 2.2 `sales_weekly` (processed, produced by code, never delivered)
| Column | Type | Rules |
|---|---|---|
| `province` | text | as above |
| `sku_id` | text | as above |
| `week_start` | date | always a Monday |
| `volume_hl` | float | >= 0; sum of the 7 daily values |

- Primary key: (`province`, `sku_id`, `week_start`).
- Only **complete weeks** (all 7 days inside the delivered date range).
- Zero-filled weeks only **between** a series' first and last active week.
- Total volume must equal the daily total over the same days.

### 2.3 `province_master` (landing, full snapshot)
| Column | Type | Example |
|---|---|---|
| `province` | text, key | SP |
| `province_name` | text | São Paulo |
| `region` | text | Sudeste |

### 2.4 `sku_master` (landing, full snapshot)
| Column | Type | Rules / example |
|---|---|---|
| `sku_id` | text, key | 38958 |
| `sku_name` | text | BRAHMA LATA 350ML |
| `brand` | text | BRAHMA |
| `pack` | text | LATA 350ML |
| `container` | text | can / bottle / keg |
| `size_ml` | int | > 0, e.g. 350 |
| `units_per_case` | int | > 0, e.g. 12 |
| `returnable` | bool | true / false |
| `launch_date` | date | ISO; empty = sold before history starts |
| `discontinue_date` | date | ISO; empty = still active |

### 2.5 `weather_weekly` (landing)
| Column | Type | Rules |
|---|---|---|
| `province` | text | in `province_master` |
| `week_start` | date | Monday |
| `temp_max_c` | float | degrees Celsius |
| `temp_min_c` | float | degrees Celsius |
| `temp_avg_c` | float | degrees Celsius |
| `precipitation` | float | >= 0; unit as provided by source (unconfirmed) |

Real values up to 2024-10-28; synthetic (climate normal + variation) after that.

### 2.6 `holidays` (landing, full snapshot)
| Column | Type | Rules |
|---|---|---|
| `date` | date | ISO |
| `province` | text | state code, or `BR` for national holidays |
| `holiday_name` | text | e.g. Carnaval |

## 3. Scope (synthetic v1)
- Time: daily from 2021-01-01 (Fri) to 2024-12-29 (Sun) in the history load; then weekly drops.
- Geography: 9 states in 3 regions (placeholders until the real `province_master` arrives).

| Region | Provinces |
|---|---|
| Sudeste | SP (São Paulo), RJ (Rio de Janeiro), MG (Minas Gerais) |
| Sul | RS (Rio Grande do Sul), PR (Paraná), SC (Santa Catarina) |
| Nordeste | BA (Bahia), PE (Pernambuco), CE (Ceará) |

- Products: 40 SKUs; about 230 active province x SKU combinations.



## 4. Landing layout
    landing/
      sellin_daily/ingest_date=2024-12-29/part.csv    history: 2021-01-01 .. 2024-12-29
      sellin_daily/ingest_date=2025-01-05/part.csv    one week: 2024-12-30 .. 2025-01-05
      weather_weekly/ingest_date=YYYY-MM-DD/part.csv
      masters/ingest_date=YYYY-MM-DD/province_master.csv
      masters/ingest_date=YYYY-MM-DD/sku_master.csv
      masters/ingest_date=YYYY-MM-DD/holidays.csv

- `ingest_date` = the **Sunday** that closes the last week contained in the drop.
- Weekly drops contain exactly one Monday-Sunday block of daily rows.
- **Append-only:** existing drops are never edited or overwritten.
  A drop whose `ingest_date` already exists is rejected.
- Masters are full snapshots; the pipeline uses the latest one.
- Locally the root is `landing/`; in production it is `s3://<bucket>/landing/`.

- A drop is complete only when its `_SUCCESS` file exists. The producer writes it
  after all data files of the drop. Readers ignore drops without it.
- A drop without `_SUCCESS` was never delivered: its producer may remove and rewrite it.


## 5. Validation checks (run on every new drop)
1. Columns exactly as listed, in any order; no extra or missing columns.
2. Types parse (dates, numbers); no empty values in key columns.
3. No duplicate keys within a drop. A later drop may restate days delivered by an
   earlier drop (a correction); the row from the latest drop wins.
4. `volume_hl` > 0 in daily data.
5. Every `province` and `sku_id` exists in the masters.
6. Dates fall inside the drop's declared range; the drop continues directly after the previous one (no gaps).
7. File is UTF-8 without BOM.
8. Only drops with a `_SUCCESS` marker are read.


## 6. Change policy
- Adding a new optional column: allowed, minor version (v1.1).
- Renaming, removing or changing the meaning or unit of a column: new major version (v2.0),
  agreed before the data changes.
- The real data must pass every rule above before it replaces the synthetic data.

## 7. Changelog
- v1.2 (2026-10-25): later drops may restate earlier days (corrections); latest drop wins.
- v1.1 (2026-10-25): `_SUCCESS` marker per drop; incomplete drops may be rewritten by the producer.
- v1.0 (2026-10-24): first version.
