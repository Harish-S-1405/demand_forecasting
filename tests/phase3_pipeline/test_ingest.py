import pandas as pd

from demandfcst import drops, storage
from demandfcst.pipeline import ingest

W1, W2 = pd.Timestamp("2025-01-05"), pd.Timestamp("2025-01-12")


def roots(tmp_path):
    return f"memory://{tmp_path.name}/landing", storage.join(tmp_path, "raw")


def make_drop(root, ingest_date, text="date,x\n2025-01-03,1.5\n", complete=True):
    storage.write_text(storage.join(drops.drop_dir(root, "sellin_daily", ingest_date), "part.csv"), text)
    if complete:
        drops.mark_complete(root, "sellin_daily", ingest_date)


def raw_bytes(root, ingest_date):
    return storage.read_head(storage.join(drops.drop_dir(root, "sellin_daily", ingest_date), "part.csv"), 10**6)


def test_complete_drop_is_copied_byte_for_byte(tmp_path):
    landing, raw = roots(tmp_path)
    make_drop(landing, W1)
    summary = ingest.ingest_new_drops(landing, raw, ["sellin_daily"])
    assert len(summary) == 1
    assert raw_bytes(raw, W1) == raw_bytes(landing, W1)
    assert drops.is_complete(raw, "sellin_daily", W1)


def test_incomplete_drop_is_not_ingested(tmp_path):
    landing, raw = roots(tmp_path)
    make_drop(landing, W1, complete=False)
    assert ingest.ingest_new_drops(landing, raw, ["sellin_daily"]).empty
    assert drops.drop_dates(raw, "sellin_daily") == []


def test_runs_are_incremental_and_repeatable(tmp_path):
    landing, raw = roots(tmp_path)
    make_drop(landing, W1)
    assert len(ingest.ingest_new_drops(landing, raw, ["sellin_daily"])) == 1
    assert len(ingest.ingest_new_drops(landing, raw, ["sellin_daily"])) == 0    # nothing new
    make_drop(landing, W2)
    summary = ingest.ingest_new_drops(landing, raw, ["sellin_daily"])
    assert list(summary["ingest_date"]) == [W2]                                  # only the new week


def test_crashed_copy_is_redone(tmp_path):
    landing, raw = roots(tmp_path)
    make_drop(landing, W1)
    storage.write_text(storage.join(drops.drop_dir(raw, "sellin_daily", W1), "part.csv"), "half")  # no marker
    assert len(ingest.ingest_new_drops(landing, raw, ["sellin_daily"])) == 1
    assert raw_bytes(raw, W1) == raw_bytes(landing, W1)


def test_answer_key_is_never_ingested():
    assert "promotions" not in ingest.DATASETS
