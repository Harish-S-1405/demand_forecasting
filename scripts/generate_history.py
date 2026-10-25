"""Generate the synthetic sell-in history and write it as the first landing drop.

Where it writes (local folders or S3) comes from configs/data.toml.
Run from the project root:
    python scripts/generate_history.py                  # storage from the config
    python scripts/generate_history.py --storage local  # override
"""

import argparse
import logging
import time

import pandas as pd

from demandfcst import config, storage
from demandfcst.synthetic import calendar, catalog, demand, landing, weather

HISTORY_START = pd.Timestamp("2021-01-01")      # Friday, like a real extract
HISTORY_END = pd.Timestamp("2024-12-29")        # Sunday: closes the last full week
HOLIDAY_YEARS = (2020, 2030)
LANDING_DATASETS = ["sellin_daily", "weather_weekly", "province_master", "sku_master", "holidays"]

log = logging.getLogger("generate_history")


def parse_args():
    p = argparse.ArgumentParser(description="Generate the synthetic history drop.")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--storage", choices=["local", "s3"], help="override 'storage' in configs/data.toml")
    return p.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    t0 = time.perf_counter()
    loc = config.locations(storage=args.storage)
    params = storage.join(loc["generator"], "generator_params.json")
    weather_source = storage.join(loc["generator"], "weather_source.csv")
    ingest = HISTORY_END
    log.info("landing: %s", loc["landing"])

    landing.ensure_new_drop(loc["landing"], LANDING_DATASETS, ingest)
    landing.ensure_new_drop(loc["truth"], ["promotions"], ingest)

    cat = catalog.build_catalog(args.seed)
    catalog.save_params(cat, params, seed=args.seed,
                        history_start=HISTORY_START, history_end=HISTORY_END)
    log.info("catalog: %d provinces, %d SKUs, %d series -> %s",
             len(cat["provinces"]), len(cat["skus"]), len(cat["series"]), params)

    wx = weather.weekly_weather(weather_source, cat["provinces"], HISTORY_START, HISTORY_END, args.seed)
    log.info("weather: %d province-weeks (%d synthetic)", len(wx), wx["is_synthetic"].sum())

    sales, promos = demand.generate_daily(HISTORY_START, HISTORY_END, cat, wx, args.seed)
    log.info("sales: %d daily rows, %.0f HL in total, %d promotions",
             len(sales), sales["volume_hl"].sum(), len(promos))
