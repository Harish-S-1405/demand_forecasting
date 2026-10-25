"""Rebuild data/processed from data/raw: validate, apply corrections, daily -> weekly.

Writes every table as Parquet (for the pipeline) and as CSV in data/processed/csv/ (for people).
Run from the project root:
    python scripts/phase3_pipeline/process.py
"""

import logging

from demandfcst import config
from demandfcst.pipeline import process

log = logging.getLogger("process")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    paths = config.pipeline_paths()
    log.info("raw: %s -> processed: %s", paths["raw"], paths["processed"])

    outputs, info = process.run(paths["raw"], paths["processed"], config.sales_start())

    for name, df in outputs.items():
        log.info("%-18s %8d rows", name, len(df))
    for r in outputs["validation_report"].itertuples():
        log.warning("%s.%s: %s", r.dataset, r.check, r.message[:120])
    log.info("weeks %s .. %s (%d), %d series, latest sales drop %s",
             info["first_week"], info["last_week"], info["weeks"], info["series"],
             info["latest_drops"]["sellin_daily"])


if __name__ == "__main__":
    main()
