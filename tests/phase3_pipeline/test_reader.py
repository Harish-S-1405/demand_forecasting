import pandas as pd
import pytest

from demandfcst import drops, storage
from demandfcst.pipeline import reader, schema

W1, W2 = pd.Timestamp("2025-01-05"), pd.Timestamp("2025-01-12")


def put(root, dataset, ingest_date, df, complete=True):
    storage.write_csv(df, storage.join(drops.drop_dir(root, dataset, ingest_date), "part.csv"))
    if complete:
        drops.mark_complete(root, dataset, ingest_date)


def sales(day, volume="1.5", sku="00123"):
    return pd.DataFrame({"date": [day], "province": ["SP"], "sku_id": [sku], "volume_hl": [volume]})


def test_drops_are_stacked_with_their_ingest_date(tmp_path):
    put(tmp_path, "sellin_daily", W1, sales("2025-01-03"))
    put(tmp_path, "sellin_daily", W2, sales("2025-01-10"))
    table = reader.read_dataset(tmp_path, "sellin_daily")
    assert list(table["ingest_date"]) == [W1, W2]
    assert list(table["sku_id"]) == ["00123", "00123"]                 # still text
    assert table["date"].dtype.kind == "M"


def test_incomplete_drops_are_skipped(tmp_path):
    put(tmp_path, "sellin_daily", W1, sales("2025-01-03"))
    put(tmp_path, "sellin_daily", W2, sales("2025-01-10"), complete=False)
    assert list(reader.read_dataset(tmp_path, "sellin_daily")["ingest_date"]) == [W1]


def test_problems_from_all_files_reported_with_their_location(tmp_path):
    put(tmp_path, "sellin_daily", W1, sales("03/01/2025"))                 # bad date
    put(tmp_path, "sellin_daily", W2, sales("2025-01-10", volume="abc"))   # bad volume
    with pytest.raises(schema.SchemaError) as err:
        reader.read_dataset(tmp_path, "sellin_daily")
    problems = err.value.problems
    assert len(problems) == 2
    assert "ingest_date=2025-01-05" in problems[0] and "date" in problems[0]
    assert "ingest_date=2025-01-12" in problems[1] and "volume_hl" in problems[1]


def test_read_latest_returns_only_the_newest_snapshot(tmp_path):
    old = pd.DataFrame({"province": ["SP"], "province_name": ["São Paulo"], "region": ["Sudeste"]})
    new = pd.concat([old, pd.DataFrame({"province": ["RJ"], "province_name": ["Rio de Janeiro"],
                                        "region": ["Sudeste"]})])
    put(tmp_path, "province_master", W1, old)
    put(tmp_path, "province_master", W2, new)
    latest = reader.read_latest(tmp_path, "province_master")
    assert list(latest["province"]) == ["SP", "RJ"]
    assert (latest["ingest_date"] == W2).all()


def test_no_drops_is_a_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="no complete sellin_daily drops"):
        reader.read_dataset(tmp_path, "sellin_daily")
