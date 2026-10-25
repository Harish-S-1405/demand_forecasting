"""Release the next synthetic week(s) into the landing area (a simulated Monday delivery).

Where it reads and writes (local folders or S3) comes from configs/data.toml.
Run from the project root:
    python scripts/release_week.py                     # one week
    python scripts/release_week.py --weeks 4           # four weeks, one drop each
    python scripts/release_week.py --storage local     # override the config
"""

import argparse
import logging

from demandfcst import config, storage
from demandfcst.synthetic import release

log = logging.getLogger("release_week")


def parse_args():
    p = argparse.ArgumentParser(description="Release the next synthetic week(s).")
    p.add_argument("--weeks", type=int, default=1, help="how many weeks to release, one drop each")
    p.add_argument("--storage", choices=["local", "s3"], help="override 'storage' in configs/data.toml")
    return p.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    loc = config.locations(storage=args.storage)
    params = storage.join(loc["generator"], "generator_params.json")
    weather_source = storage.join(loc["generator"], "weather_source.csv")
    log.info("landing: %s", loc["landing"])
    for _ in range(args.weeks):
        release.release_next_week(loc["landing"], loc["truth"], params, weather_source)


if __name__ == "__main__":
    main()
