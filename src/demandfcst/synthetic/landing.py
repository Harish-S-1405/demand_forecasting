"""Write generator output as landing drops, following the data contract layout:

    <root>/<dataset>/ingest_date=YYYY-MM-DD/<file>.csv

Drops are append-only: writing to an ingest_date that already exists is refused.
Locally <root> is the landing/ folder; later it becomes s3://<bucket>/landing/.
"""

from pathlib import Path

PROVINCE_MASTER_COLUMNS = ["province", "province_name", "region"]
SKU_MASTER_COLUMNS = ["sku_id", "sku_name", "brand", "pack", "container", "size_ml",
                      "units_per_case", "returnable", "launch_date", "discontinue_date"]


def drop_dir(root, dataset, ingest_date):
    return Path(root) / dataset / f"ingest_date={ingest_date:%Y-%m-%d}"


def ensure_new_drop(root, datasets, ingest_date):
    """Stop before generating anything if any of these datasets already has this drop."""
    existing = [d for d in datasets if drop_dir(root, d, ingest_date).exists()]
    if existing:
        raise FileExistsError(
            f"ingest_date={ingest_date:%Y-%m-%d} already exists for {existing} under {root}. "
            "Landing drops are append-only; delete them yourself only if you really mean to regenerate.")


def write_drop(df, root, dataset, ingest_date, filename="part.csv"):
    """Write one file of a drop as UTF-8 CSV (no BOM, ISO dates). Returns the path."""
    path = drop_dir(root, dataset, ingest_date) / filename
    if path.exists():
        raise FileExistsError(f"{path} already exists; landing drops are append-only")
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, date_format="%Y-%m-%d", encoding="utf-8")
    return path


def province_master(catalog):
    return catalog["provinces"][PROVINCE_MASTER_COLUMNS]


def sku_master(catalog):
    return catalog["skus"][SKU_MASTER_COLUMNS]
