"""Daily -> weekly sell-in (contract v1.3, sales_weekly).

Complete Monday-Sunday weeks only; volume is never lost or invented; zero weeks are
filled from each series' first sale to the latest complete week, or to its SKU's
discontinuation week. Input must be deduplicated first (dedupe.latest_wins).
"""

import numpy as np
import pandas as pd

KEY = ["province", "sku_id", "week_start"]
DAILY_KEY = ["province", "sku_id", "date"]


def monday(dates):
    """Monday of the Monday-Sunday week each date falls in (works with NaT)."""
    return dates - pd.to_timedelta(dates.dt.day_of_week, unit="D")


def complete_weeks(start, end):
    """(first, last) Monday of the complete weeks inside start..end."""
    first = start + pd.Timedelta(days=(7 - start.day_of_week) % 7)          # first Monday on/after start
    last_sunday = end - pd.Timedelta(days=(end.day_of_week + 1) % 7)        # last Sunday on/before end
    return first, last_sunday - pd.Timedelta(days=6)


def to_weekly(daily, skus, start, end):
    """Weekly sell-in per province x SKU for the complete weeks inside start..end.

    daily: deduplicated rows with date, province, sku_id, volume_hl.
    skus: needs sku_id and discontinue_date (from sku_master).
    Returns the sales_weekly contract table: province, sku_id, week_start, volume_hl.
    """
    if daily.duplicated(DAILY_KEY).any():
        raise ValueError("daily sales still contain duplicate days: deduplicate first (dedupe.latest_wins)")
    first_week, last_week = complete_weeks(start, end)

    d = daily.assign(week_start=monday(daily["date"]))
    d = d[(d["week_start"] >= first_week) & (d["week_start"] <= last_week)]
    weekly = d.groupby(KEY, as_index=False)["volume_hl"].sum()

    # active life: first week with sales -> latest complete week, or the discontinuation week
    span = weekly.groupby(["province", "sku_id"])["week_start"].agg(first="min", last_sale="max").reset_index()
    disc = span["sku_id"].map(skus.drop_duplicates("sku_id").set_index("sku_id")["discontinue_date"])
    end_week = monday(disc).where(monday(disc) < last_week, last_week)     # NaT (still active) -> last_week
    span["last"] = pd.concat([span["last_sale"], end_week], axis=1).max(axis=1)   # never cut real sales

    grid = pd.concat([pd.DataFrame({"province": s.province, "sku_id": s.sku_id,
                                    "week_start": pd.date_range(s.first, s.last, freq="7D")})
                      for s in span.itertuples(index=False)], ignore_index=True)
    out = (grid.merge(weekly, on=KEY, how="left")
               .fillna({"volume_hl": 0.0})
               .sort_values(KEY).reset_index(drop=True))

    if not np.isclose(out["volume_hl"].sum(), d["volume_hl"].sum()):
        raise ValueError(f"weekly total {out['volume_hl'].sum():.3f} HL != daily total "
                         f"{d['volume_hl'].sum():.3f} HL for the same weeks")
    return out[KEY + ["volume_hl"]]
