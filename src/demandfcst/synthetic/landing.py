"""Write generator output as landing drops, following the data contract layout:

    <root>/<dataset>/ingest_date=YYYY-MM-DD/<file>.csv

Drops are append-only: writing to an ingest_date that already exists is refused.
<root> is a local folder or an S3 URL (see demandfcst.storage).
"""

from demandfcst import storage

PROVINCE_MASTER_COLUMNS = ["province", "province_name", "region"]
SKU_MASTER_COLUMNS = ["sku_id", "sku_name", "brand", "pack", "container", "size_ml",
                      "units_per_case", "returnable", "launch_date", "discontinue_date"]


def drop_dir(root, dataset, ingest_date):
    return storage.join(root, dataset, f"ingest_date={ingest_date:%Y-%m-%d}")


def ensure_new_drop(root, datasets, ingest_date):
    """Stop before generating anything if any of these datasets already has this drop."""
    existing = [d for d in datasets if storage.exists(drop_dir(root, d, ingest_date))]
    if existing:
        raise FileExistsError(
            f"ingest_date={ingest_date:%Y-%m-%d} already exists for {existing} under {root}. "
            "Landing drops are append-only; delete them yourself only if you really mean to regenerate.")


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
