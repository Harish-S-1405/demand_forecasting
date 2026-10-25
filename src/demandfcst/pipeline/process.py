"""Processing: raw drops -> validated, corrected, weekly tables in data/processed/.

Full rebuild every run, so the outputs always reflect every correction received:
read all raw drops -> validate (stop on errors, outputs untouched) -> latest drop wins ->
daily to weekly -> write every table as Parquet (pipeline) and CSV (people) into a staging
folder -> swap it in, so data/processed is always either the old or the new complete set.
"""

import json
import logging

import pandas as pd

from demandfcst import drops, storage
from demandfcst.pipeline import dedupe, reader, validate, weekly
from demandfcst.pipeline.schema import SCHEMAS

log = logging.getLogger(__name__)


def check_weekly(df):
    """The weekly table must match the sales_weekly contract before it is written."""
    spec = SCHEMAS["sales_weekly"]
    problems = []
    if list(df.columns) != spec.column_names:
        problems.append(f"columns {list(df.columns)} != {spec.column_names}")
    if df.duplicated(list(spec.key)).any():
        problems.append("duplicate province-sku-week rows")
    if (df["week_start"].dt.day_of_week != 0).any():
        problems.append("week_start values that are not Mondays")
    if (df["volume_hl"] < 0).any():
        problems.append("negative volumes")
    if problems:
        raise ValueError("sales_weekly breaks the contract: " + "; ".join(problems))


def build(tables, sales_start, sales_end):
    """Every processed table, from the typed raw tables (already validated)."""
    current, superseded = dedupe.latest_wins(tables["sellin_daily"], validate.SALES_KEY)
    sales_weekly = weekly.to_weekly(current, tables["sku_master"], sales_start, sales_end)
    check_weekly(sales_weekly)
    return {
        "sales_weekly": sales_weekly,
        "sales_daily": current.sort_values(["date", "province", "sku_id"]).reset_index(drop=True),
        "restatements": dedupe.restatement_summary(current, superseded, validate.SALES_KEY),
        "weather_weekly": tables["weather_weekly"].sort_values(validate.WEATHER_KEY).reset_index(drop=True),
        "province_master": tables["province_master"],
        "sku_master": tables["sku_master"],
        "holidays": tables["holidays"],
    }


def run_info(outputs, raw_root, sales_start, sales_end):
    """What this run produced, from which deliveries: saved as run_info.json."""
    sw, report = outputs["sales_weekly"], outputs["validation_report"]
    datasets = reader.EVENT_DATASETS + reader.SNAPSHOT_DATASETS
    return {
        "processed_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "sales_start": f"{sales_start:%Y-%m-%d}",
        "sales_end": f"{sales_end:%Y-%m-%d}",
        "first_week": f"{sw['week_start'].min():%Y-%m-%d}",
        "last_week": f"{sw['week_start'].max():%Y-%m-%d}",
        "weeks": int(sw["week_start"].nunique()),
        "series": int(sw.groupby(["province", "sku_id"]).ngroups),
        "latest_drops": {d: f"{drops.drop_dates(raw_root, d)[-1]:%Y-%m-%d}" for d in datasets},
        "rows": {name: int(len(df)) for name, df in outputs.items()},
        "warnings": int((report["level"] == "warning").sum()),
    }


def run(raw_root, processed_root, sales_start):
    """Rebuild data/processed from raw. Raises ValidationError, before writing anything, if raw has errors."""
    tables = reader.read_all(raw_root)
    report = validate.validate(tables)
    validate.raise_if_errors(report)                           # stop: previous outputs stay untouched

    sales_end = drops.drop_dates(raw_root, "sellin_daily")[-1]
    outputs = build(tables, sales_start, sales_end)
    outputs["validation_report"] = report
    info = run_info(outputs, raw_root, sales_start, sales_end)

    staging = processed_root.rstrip("/") + "_staging"
    storage.remove(staging)
    for name, df in outputs.items():
        storage.write_parquet(df, storage.join(staging, f"{name}.parquet"))
        storage.write_csv(df, storage.join(staging, "csv", f"{name}.csv"), date_format="%Y-%m-%d")
    storage.write_text(storage.join(staging, "run_info.json"), json.dumps(info, indent=2))
    storage.touch(storage.join(staging, drops.SUCCESS))

    storage.remove(processed_root)                             # swap: old out ...
    storage.move(staging, processed_root)                      # ... new in
    return outputs, info
