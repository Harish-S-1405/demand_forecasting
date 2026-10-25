"""Ingestion: copy new, complete drops from the landing area into data/raw/, byte for byte.

Only drops with a _SUCCESS marker are copied (contract v1.1). Drops already complete in
raw are skipped, so runs are incremental and safe to repeat. Raw is an exact mirror of
what arrived: nothing is parsed, fixed or filtered here. Validation happens in processing.
The answer key (truth/) is never ingested.
"""

import logging

import pandas as pd

from demandfcst import drops, storage

log = logging.getLogger(__name__)

DATASETS = ["sellin_daily", "weather_weekly", "province_master", "sku_master", "holidays"]


def drop_files(root, dataset, ingest_date):
    """Data files of a drop: everything except the _SUCCESS marker."""
    names = storage.list_files(drops.drop_dir(root, dataset, ingest_date))
    return [n for n in names if n != drops.SUCCESS]


def ingest_drop(landing_root, raw_root, dataset, ingest_date):
    """Copy one complete drop into raw, then mark it complete there. Returns bytes copied."""
    src = drops.drop_dir(landing_root, dataset, ingest_date)
    dst = drops.drop_dir(raw_root, dataset, ingest_date)
    storage.remove(dst)                                     # clears a copy left by a crashed run
    copied = 0
    for name in drop_files(landing_root, dataset, ingest_date):
        copied += storage.copy_file(storage.join(src, name), storage.join(dst, name))
    drops.mark_complete(raw_root, dataset, ingest_date)     # last: the raw copy is complete
    return copied


def ingest_new_drops(landing_root, raw_root, datasets=DATASETS):
    """Copy every complete landing drop that raw doesn't have yet. Returns a summary table."""
    rows = []
    for dataset in datasets:
        already = set(drops.drop_dates(raw_root, dataset))
        for ingest_date in drops.drop_dates(landing_root, dataset):
            if ingest_date in already:
                continue
            n_bytes = ingest_drop(landing_root, raw_root, dataset, ingest_date)
            rows.append((dataset, ingest_date, n_bytes))
            log.info("ingested %s/ingest_date=%s (%d bytes)", dataset, f"{ingest_date:%Y-%m-%d}", n_bytes)
    summary = pd.DataFrame(rows, columns=["dataset", "ingest_date", "bytes"])
    log.info("%d new drops ingested", len(summary))
    return summary
