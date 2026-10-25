"""Copy new, complete drops from the landing area into data/raw/.

The landing location (S3 or local) comes from configs/data.toml.
Run from the project root:
    python scripts/phase3_pipeline/ingest.py
    python scripts/phase3_pipeline/ingest.py --storage local
"""

import argparse
import logging

from demandfcst import config
from demandfcst.pipeline import ingest

log = logging.getLogger("ingest")


def main():
    p = argparse.ArgumentParser(description="Ingest new complete landing drops into data/raw/.")
    p.add_argument("--storage", choices=["local", "s3"], help="override 'storage' in configs/data.toml")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    landing_root = config.locations(storage=args.storage)["landing"]
    raw_root = config.pipeline_paths()["raw"]
    log.info("landing: %s -> raw: %s", landing_root, raw_root)
    ingest.ingest_new_drops(landing_root, raw_root)


if __name__ == "__main__":
    main()
