"""Load processed tables for analysis. Read-only: EDA never writes to data/."""

import pandas as pd

from demandfcst import config, storage

MASTER_DROP = ["ingest_date"]       # bookkeeping column from the reader, not an attribute


def load(name, processed=None):
    """One processed table (e.g. "sales_weekly") from data/processed."""
    processed = processed or config.pipeline_paths()["processed"]
    return pd.read_parquet(storage.join(processed, f"{name}.parquet"))


def weekly_enriched(processed=None):
    """sales_weekly joined with geography, product attributes and calendar columns."""
    sw = load("sales_weekly", processed)
    provinces = load("province_master", processed).drop(columns=MASTER_DROP, errors="ignore")
    skus = load("sku_master", processed).drop(columns=MASTER_DROP, errors="ignore")

    out = (sw.merge(provinces, on="province", how="left", validate="many_to_one")
             .merge(skus, on="sku_id", how="left", validate="many_to_one"))
    iso = out["week_start"].dt.isocalendar()
    out["year"] = iso["year"].astype(int)
    out["week_of_year"] = iso["week"].astype(int)
    out["month"] = out["week_start"].dt.month
    out["series"] = out["province"] + "·" + out["sku_id"]
    return out
