"""Simulated weekly delivery: generate the next Monday-Sunday week and append it as new drops.

Each call continues from the latest sellin_daily drop, reuses the saved generator params
(same series, same settings, same seed) and writes one new ingest_date.
"""

import logging
from demandfcst import storage


import pandas as pd

from demandfcst.synthetic import catalog, demand, landing, weather, corrections

from demandfcst.drops import drop_dates  # noqa: F401 (re-exported)


log = logging.getLogger(__name__)

SALES = "sellin_daily"
WEATHER = "weather_weekly"
PROMOS = "promotions"
CORRECTIONS = "corrections"







def next_week(after):
    """Monday..Sunday of the week right after the Sunday `after`."""
    if after.day_of_week != 6:
        raise ValueError(f"last drop ends on {after:%Y-%m-%d}, which is not a Sunday")
    return after + pd.Timedelta(days=1), after + pd.Timedelta(days=7)


def release_next_week(landing_root, truth_root, params_path, weather_source, correction_prob=0.0):
    """Generate the week after the latest sales drop and write it as new drops.

    correction_prob: chance (0..1) that this release also re-sends some earlier days with
    revised volumes (see synthetic.corrections). 0 = never.
    Returns the new ingest_date (the Sunday that closes the released week).
    """
    dates = drop_dates(landing_root, SALES)
    if not dates:
        raise FileNotFoundError(f"no {SALES} drops under {landing_root}; run generate_history.py first")
    monday, sunday = next_week(dates[-1])

    landing.ensure_new_drop(landing_root, [SALES, WEATHER], sunday)
    landing.ensure_new_drop(truth_root, [PROMOS, CORRECTIONS], sunday)

    cat, meta = catalog.load_params(params_path)
    seed = meta["seed"]
    wx = weather.weekly_weather(weather_source, cat["provinces"], monday, sunday, seed)
    sales, promos = demand.generate_daily(monday, sunday, cat, wx, seed)
    fixes = corrections.corrections_for(monday, cat, weather_source, seed, correction_prob)
    if len(fixes):
        sales = (pd.concat([sales, fixes[sales.columns]], ignore_index=True)
                 .sort_values(["date", "province", "sku_id"]).reset_index(drop=True))

    landing.write_drop(sales, landing_root, SALES, sunday)
    landing.write_drop(wx[weather.WEATHER_COLUMNS], landing_root, WEATHER, sunday)
    landing.write_drop(promos, truth_root, PROMOS, sunday)
    landing.write_drop(fixes, truth_root, CORRECTIONS, sunday)
    landing.mark_complete(truth_root, CORRECTIONS, sunday)
    landing.mark_complete(truth_root, PROMOS, sunday)
    landing.mark_complete(landing_root, WEATHER, sunday)
    landing.mark_complete(landing_root, SALES, sunday)        # last: now the week counts as released
    log.info("released %s .. %s: %d sales rows (%d corrections), %.0f HL, %d promotions",
             f"{monday:%Y-%m-%d}", f"{sunday:%Y-%m-%d}", len(sales), len(fixes),
             sales["volume_hl"].sum(), len(promos))
    return sunday

