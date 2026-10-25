"""Read raw drops into typed tables, following the contract schema.

read_dataset: every complete drop of a dataset stacked into one table (event data such
as sales and weather), plus ingest_date: which drop each row came from.
read_latest: only the newest complete drop (full snapshots such as the masters).
Files that break the contract are all reported together, each with its location.
"""

import pandas as pd

from demandfcst import drops, storage
from demandfcst.pipeline import schema


def _read_drop(root, dataset, ingest_date):
    """Typed tables of one drop's files, plus the problems found (each prefixed with its file)."""
    spec = schema.SCHEMAS[dataset]
    folder = drops.drop_dir(root, dataset, ingest_date)
    names = drops.data_files(root, dataset, ingest_date)
    if not names:
        return [], [f"{folder}: complete drop has no data files"]
    tables, problems = [], []
    for name in names:
        location = storage.join(folder, name)
        try:
            tables.append(schema.read_csv(location, spec))
        except schema.SchemaError as e:
            problems += [f"{location}: {p}" for p in e.problems]
    return tables, problems


def read_dataset(root, dataset):
    """Every complete drop of a dataset as one typed table, with an ingest_date column."""
    dates = drops.drop_dates(root, dataset)
    if not dates:
        raise FileNotFoundError(f"no complete {dataset} drops under {root}")
    tables, problems = [], []
    for ingest_date in dates:
        found, bad = _read_drop(root, dataset, ingest_date)
        tables += [t.assign(ingest_date=ingest_date) for t in found]
        problems += bad
    if problems:
        raise schema.SchemaError(dataset, problems)
    return pd.concat(tables, ignore_index=True)


def read_latest(root, dataset):
    """The newest complete drop of a snapshot dataset (e.g. sku_master), with its ingest_date."""
    dates = drops.drop_dates(root, dataset)
    if not dates:
        raise FileNotFoundError(f"no complete {dataset} drops under {root}")
    tables, problems = _read_drop(root, dataset, dates[-1])
    if problems:
        raise schema.SchemaError(dataset, problems)
    return pd.concat(tables, ignore_index=True).assign(ingest_date=dates[-1])

EVENT_DATASETS = ["sellin_daily", "weather_weekly"]
SNAPSHOT_DATASETS = ["province_master", "sku_master", "holidays"]


def read_all(root):
    """Every contract table from raw: event datasets stacked, snapshots from their latest drop."""
    tables = {name: read_dataset(root, name) for name in EVENT_DATASETS}
    tables.update({name: read_latest(root, name) for name in SNAPSHOT_DATASETS})
    return tables
