"""Corrections: when the same day arrives in more than one drop, the latest drop wins (contract v1.2).

Superseded rows are returned, not thrown away, so every restatement can be reported.
"""

import pandas as pd

SUMMARY_COLUMNS = ["ingest_date", "restated_days", "hl_before", "hl_after", "hl_change"]


def latest_wins(df, key, order="ingest_date"):
    """For every key keep the row from the latest drop. Returns (current, superseded)."""
    ordered = df.sort_values([*key, order], kind="stable")
    is_latest = ~ordered.duplicated(key, keep="last")
    return ordered[is_latest].reset_index(drop=True), ordered[~is_latest].reset_index(drop=True)


def restatement_summary(current, superseded, key, value="volume_hl"):
    """Per correcting drop: how many days it restated and how the volume changed."""
    if superseded.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)
    previous = superseded.drop_duplicates(key, keep="last")[[*key, value]]   # the value just before
    both = current.merge(previous, on=key, suffixes=("", "_before"))
    out = (both.groupby("ingest_date")
               .agg(restated_days=(value, "size"), hl_before=(f"{value}_before", "sum"), hl_after=(value, "sum"))
               .reset_index())
    out["hl_change"] = out["hl_after"] - out["hl_before"]
    return out[SUMMARY_COLUMNS]
