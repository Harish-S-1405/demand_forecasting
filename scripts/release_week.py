"""Release the next synthetic week(s) into the landing area (a simulated Monday delivery).

Run from the project root:
    python scripts/release_week.py             # one week
    python scripts/release_week.py --weeks 4   # four weeks, one drop each
"""

import argparse
import logging
from pathlib import Path

from demandfcst.synthetic import release

ROOT = Path(__file__).resolve().parents[1]


def parse_args():
    p = argparse.ArgumentParser(description="Release the next synthetic week(s).")
    p.add_argument("--weeks", type=int, default=1, help="how many weeks to release, one drop each")
    p.add_argument("--landing", type=Path, default=ROOT / "landing")
    p.add_argument("--truth", type=Path, default=ROOT / "data" / "truth")
    p.add_argument("--params", type=Path, default=ROOT / "data" / "generator" / "generator_params.json")
    p.add_argument("--weather-source", type=Path, default=ROOT / "data" / "raw" / "source" / "weather_source.csv")
    return p.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for _ in range(args.weeks):
        release.release_next_week(args.landing, args.truth, args.params, args.weather_source)


if __name__ == "__main__":
    main()
