# Pipeline fixes found during the data diagnostic

Collected during the audit and applied together at the end of 4.1, then the pipeline is re-run
and the affected analyses re-checked.

| ID | Problem | Found in | Fix | Contract change | Status |
|---|---|---|---|---|---|
| PF-01 | The weekly table starts each series at its first sale, so sparse series lose real zero weeks before their first order (12 series, up to 4 weeks) | I-01 (4.1 step 1) | Active life starts at the data start for products that existed before it, and at the launch week for launched SKUs (sku_master.launch_date); ends at the discontinuation week as now | v1.4: sales_weekly zero-fill rule | open |
    