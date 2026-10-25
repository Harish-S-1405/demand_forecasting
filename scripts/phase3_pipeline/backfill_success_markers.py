"""One-off migration: add _SUCCESS markers to drops written before contract v1.1.

Every drop that exists now was verified complete in Phase 2 (S3.4), so each gets a marker.
Dry run by default; pass --apply to write.
    python scripts/phase3_pipeline/backfill_success_markers.py
    python scripts/phase3_pipeline/backfill_success_markers.py --apply
"""

import argparse
import logging

import pandas as pd

from demandfcst import config, storage
from demandfcst.synthetic import landing

DATASETS = {
    "landing": ["sellin_daily", "weather_weekly", "province_master", "sku_master", "holidays"],
    "truth": ["promotions"],
}

log = logging.getLogger("backfill_success_markers")


def main():
    p = argparse.ArgumentParser(description="Add _SUCCESS markers to pre-v1.1 drops.")
    p.add_argument("--apply", action="store_true", help="write the markers (default: dry run)")
    p.add_argument("--storage", choices=["local", "s3"], help="override 'storage' in configs/data.toml")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    loc = config.locations(storage=args.storage)
    todo = 0
    for area, datasets in DATASETS.items():
        for dataset in datasets:
            for name in storage.list_dirs(storage.join(loc[area], dataset), "ingest_date=*"):
                ingest = pd.Timestamp(name.split("=", 1)[1])
                if landing.is_complete(loc[area], dataset, ingest):
                    continue
                todo += 1
                log.info("%s %s/%s/%s", "marking" if args.apply else "would mark", area, dataset, name)
                if args.apply:
                    landing.mark_complete(loc[area], dataset, ingest)
    log.info("%d drops %s", todo, "marked" if args.apply else "need a marker (dry run: nothing written)")


if __name__ == "__main__":
    main()
