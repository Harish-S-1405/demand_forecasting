"""Generate the synthetic sell-in history and write it as the first landing drop.

Run from the project root:
    python scripts/generate_history.py
"""

import argparse
import logging
import time
from pathlib import Path

import pandas as pd

from demandfcst.synthetic import calendar, catalog, demand, landing, weather

ROOT = Path(__file__).resolve().parents[1]
HISTORY_START = pd.Timestamp("2021-01-01")      # Friday, like a real extract
HISTORY_END = pd.Timestamp("2024-12-29")        # Sunday: closes the last full week
HOLIDAY_YEARS = (2020, 2030)

log = logging.getLogger("generate_history")


def parse_args():
    p = argparse.ArgumentParser(description="Generate the synthetic history drop.")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--landing", type=Path, default=ROOT / "landing")
    p.add_argument("--truth", type=Path, default=ROOT / "data" / "truth")
    p.add_argument("--params", type=Path, default=ROOT / "data" / "generator" / "generator_params.json")
    p.add_argument("--weather-source", type=Path, default=ROOT / "data" / "raw" / "source" / "weather_source.csv")
    return p.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    t0 = time.perf_counter()
    ingest = HISTORY_END

    landing.ensure_new_drop(args.landing, ["sellin_daily", "weather_weekly", "masters"], ingest)
    landing.ensure_new_drop(args.truth, ["promotions"], ingest)

    cat = catalog.build_catalog(args.seed)
    catalog.save_params(cat, args.params, seed=args.seed,
                        history_start=HISTORY_START, history_end=HISTORY_END)
    log.info("catalog: %d provinces, %d SKUs, %d series -> %s",
             len(cat["provinces"]), len(cat["skus"]), len(cat["series"]), args.params)

    wx = weather.weekly_weather(args.weather_source, cat["provinces"], HISTORY_START, HISTORY_END, args.seed)
    log.info("weather: %d province-weeks (%d synthetic)", len(wx), wx["is_synthetic"].sum())

    sales, promos = demand.generate_daily(HISTORY_START, HISTORY_END, cat, wx, args.seed)
    log.info("sales: %d daily rows, %.0f HL in total, %d promotions",
             len(sales), sales["volume_hl"].sum(), len(promos))

    outputs = [
        (sales, args.landing, "sellin_daily", "part.csv"),
        (wx[weather.WEATHER_COLUMNS], args.landing, "weather_weekly", "part.csv"),
        (landing.province_master(cat), args.landing, "masters", "province_master.csv"),
        (landing.sku_master(cat), args.landing, "masters", "sku_master.csv"),
        (calendar.holiday_calendar(*HOLIDAY_YEARS), args.landing, "masters", "holidays.csv"),
        (promos, args.truth, "promotions", "part.csv"),
    ]
    for df, root, dataset, filename in outputs:
        path = landing.write_drop(df, root, dataset, ingest, filename)
        log.info("wrote %s (%d rows)", path, len(df))

    log.info("done in %.1fs", time.perf_counter() - t0)


if __name__ == "__main__":
    main()
