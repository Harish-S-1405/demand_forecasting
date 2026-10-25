"""The contract's drop layout, shared by producers (generator, real extract) and consumers (pipeline):

    <root>/<dataset>/ingest_date=YYYY-MM-DD/part.csv
    <root>/<dataset>/ingest_date=YYYY-MM-DD/_SUCCESS     written last: the drop is complete
"""

import pandas as pd

from demandfcst import storage

SUCCESS = "_SUCCESS"


def drop_dir(root, dataset, ingest_date):
    return storage.join(root, dataset, f"ingest_date={ingest_date:%Y-%m-%d}")


def is_complete(root, dataset, ingest_date):
    """A drop counts as delivered only when its _SUCCESS marker exists."""
    return storage.exists(storage.join(drop_dir(root, dataset, ingest_date), SUCCESS))


def mark_complete(root, dataset, ingest_date):
    """Write the _SUCCESS marker. Call only after every file of the drop has been written."""
    storage.touch(storage.join(drop_dir(root, dataset, ingest_date), SUCCESS))

def data_files(root, dataset, ingest_date):
    """Names of a drop's data files: everything except the _SUCCESS marker."""
    return [n for n in storage.list_files(drop_dir(root, dataset, ingest_date)) if n != SUCCESS]



def drop_dates(root, dataset, complete_only=True):
    """ingest_date of every drop of a dataset, oldest first (only complete drops by default)."""
    names = storage.list_dirs(storage.join(root, dataset), "ingest_date=*")
    dates = sorted(pd.Timestamp(name.split("=", 1)[1]) for name in names)
    if complete_only:
        dates = [d for d in dates if is_complete(root, dataset, d)]
    return dates
