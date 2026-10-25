"""Write generator output as landing drops, following the data contract layout:

    <root>/<dataset>/ingest_date=YYYY-MM-DD/<file>.csv

Drops are append-only: writing to an ingest_date that already exists is refused.
<root> is a local folder or an S3 URL (see demandfcst.storage).
"""

import logging

from demandfcst import storage
from demandfcst.drops import SUCCESS, drop_dir, is_complete, mark_complete  # noqa: F401 (re-exported)


log = logging.getLogger(__name__)




PROVINCE_MASTER_COLUMNS = ["province", "province_name", "region"]
SKU_MASTER_COLUMNS = ["sku_id", "sku_name", "brand", "pack", "container", "size_ml",
                      "units_per_case", "returnable", "launch_date", "discontinue_date"]



def ensure_new_drop(root, datasets, ingest_date):
    """Refuse if a complete drop already exists; clear incomplete ones left by a crashed run."""
    complete = [d for d in datasets if is_complete(root, d, ingest_date)]
    if complete:
        raise FileExistsError(
            f"ingest_date={ingest_date:%Y-%m-%d} is already delivered for {complete} under {root}. "
            "Landing drops are append-only.")
    for d in datasets:
        folder = drop_dir(root, d, ingest_date)
        if storage.exists(folder):
            log.warning("removing incomplete drop %s (no %s marker: an earlier run crashed)", folder, SUCCESS)
            storage.remove(folder)


def write_drop(df, root, dataset, ingest_date, filename="part.csv"):
    """Write one file of a drop as UTF-8 CSV (no BOM, ISO dates). Returns its location."""
    location = storage.join(drop_dir(root, dataset, ingest_date), filename)
    if storage.exists(location):
        raise FileExistsError(f"{location} already exists; landing drops are append-only")
    storage.write_csv(df, location, date_format="%Y-%m-%d")
    return location



def province_master(catalog):
    return catalog["provinces"][PROVINCE_MASTER_COLUMNS]


def sku_master(catalog):
    return catalog["skus"][SKU_MASTER_COLUMNS]
