"""Simulated weekly delivery: generate the next Monday-Sunday week and append it as new drops.

Each call continues from the latest sellin_daily drop, reuses the saved generator params
(same series, same settings, same seed) and writes one new ingest_date.
"""

import logging
from demandfcst import storage


import pandas as pd

from demandfcst.synthetic import catalog, demand, landing, weather

log = logging.getLogger(__name__)

SALES = "sellin_daily"
WEATHER = "weather_weekly"
PROMOS = "promotions"


def drop_dates(root, dataset, complete_only=True):
    """ingest_date of every drop of a dataset, oldest first (only complete drops by default)."""
    names = storage.list_dirs(storage.join(root, dataset), "ingest_date=*")
    dates = sorted(pd.Timestamp(name.split("=", 1)[1]) for name in names)
    if complete_only:
        dates = [d for d in dates if landing.is_complete(root, dataset, d)]
    return dates




def next_week(after):
    """Monday..Sunday of the week right after the Sunday `after`."""
    if after.day_of_week != 6:
        raise ValueError(f"last drop ends on {after:%Y-%m-%d}, which is not a Sunday")
    return after + pd.Timedelta(days=1), after + pd.Timedelta(days=7)


def release_next_week(landing_root, truth_root, params_path, weather_source):
    """Generate the week after the latest sales drop and write it as new drops.

    Returns the new ingest_date (the Sunday that closes the released week).
    """
    dates = drop_dates(landing_root, SALES)
    if not dates:
        raise FileNotFoundError(f"no {SALES} drops under {landing_root}; run generate_history.py first")
    monday, sunday = next_week(dates[-1])

    landing.ensure_new_drop(landing_root, [SALES, WEATHER], sunday)
    landing.ensure_new_drop(truth_root, [PROMOS], sunday)

    cat, meta = catalog.load_params(params_path)
    seed = meta["seed"]
    wx = weather.weekly_weather(weather_source, cat["provinces"], monday, sunday, seed)
    sales, promos = demand.generate_daily(monday, sunday, cat, wx, seed)

    landing.write_drop(sales, landing_root, SALES, sunday)
    landing.write_drop(wx[weather.WEATHER_COLUMNS], landing_root, WEATHER, sunday)
    landing.write_drop(promos, truth_root, PROMOS, sunday)

    landing.mark_complete(truth_root, PROMOS, sunday)
    landing.mark_complete(landing_root, WEATHER, sunday)
    landing.mark_complete(landing_root, SALES, sunday)        # last: now the week counts as released

    log.info("released %s .. %s: %d sales rows, %.0f HL, %d promotions",
             f"{monday:%Y-%m-%d}", f"{sunday:%Y-%m-%d}", len(sales), sales["volume_hl"].sum(), len(promos))
    return sunday
