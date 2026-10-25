"""Sanity checks against history: is the latest week plausible, not just valid?

Validation catches broken data. These checks catch valid but surprising data: a total far
from last week or last year, fewer active series than usual, a region's share jumping.
Results are "pass" or "warning" (for a person to look at), never errors.
"""

import pandas as pd

COLUMNS = ["check", "value", "expected", "status", "note"]
WOW_TOLERANCE = 0.40          # latest week vs the week before
YOY_TOLERANCE = 0.25          # latest week vs the same week last year
ACTIVE_DROP = 0.20            # active series may fall at most 20% below their recent average
SHARE_SHIFT_PTS = 5.0         # a region's share may move at most 5 percentage points
BASELINE_WEEKS = 8


def _row(check, value, expected, ok, note):
    return {"check": check, "value": value, "expected": expected,
            "status": "pass" if ok else "warning", "note": note}


def sanity_checks(sales_weekly, provinces):
    """Compare the latest week of the weekly table with its history. One row per check."""
    totals = sales_weekly.groupby("week_start")["volume_hl"].sum()
    latest = totals.index.max()
    prev = latest - pd.Timedelta(weeks=1)
    rows = []

    for check, other, tolerance, note in [
        ("total_vs_last_week", prev, WOW_TOLERANCE, "week before"),
        ("total_vs_last_year", latest - pd.Timedelta(weeks=52), YOY_TOLERANCE,
         "same week 52 weeks earlier; moving holidays (e.g. Carnival) can explain a gap"),
    ]:
        if other in totals.index:
            change = totals[latest] / totals[other] - 1
            rows.append(_row(check, f"{change:+.1%}", f"within ±{tolerance:.0%}", abs(change) <= tolerance,
                             f"{totals[latest]:,.0f} HL vs {totals[other]:,.0f} HL ({note})"))

    active = (sales_weekly["volume_hl"] > 0).groupby(sales_weekly["week_start"]).sum()
    baseline = active.loc[:prev].tail(BASELINE_WEEKS).mean()
    if pd.notna(baseline):
        floor = (1 - ACTIVE_DROP) * baseline
        rows.append(_row("active_series", str(int(active[latest])), f">= {floor:.0f}", active[latest] >= floor,
                         f"series with sales this week; {BASELINE_WEEKS}-week average {baseline:.0f}"))

    by_region = (sales_weekly.merge(provinces[["province", "region"]], on="province")
                 .pivot_table(index="week_start", columns="region", values="volume_hl", aggfunc="sum"))
    share = by_region.div(by_region.sum(axis=1), axis=0) * 100
    usual = share.loc[:prev].tail(BASELINE_WEEKS).mean()
    for region, now in share.loc[latest].items():
        if pd.notna(usual[region]):
            shift = now - usual[region]
            rows.append(_row(f"share_{region}", f"{now:.1f}%", f"{usual[region]:.1f}% ± {SHARE_SHIFT_PTS:.0f} pts",
                             abs(shift) <= SHARE_SHIFT_PTS, f"{shift:+.1f} pts vs the previous {BASELINE_WEEKS} weeks"))
    return pd.DataFrame(rows, columns=COLUMNS)
