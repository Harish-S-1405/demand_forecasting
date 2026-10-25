import pandas as pd

from demandfcst import storage


def test_csv_round_trip_on_memory_store(tmp_path):
    location = storage.join(f"memory://{tmp_path.name}", "landing", "sellin_daily",
                            "ingest_date=2024-12-29", "part.csv")
    df = pd.DataFrame({"sku_id": ["00123"], "volume_hl": [1.5]})
    storage.write_csv(df, location)
    assert storage.exists(location)
    pd.testing.assert_frame_equal(pd.read_csv(location, dtype={"sku_id": str}), df, check_dtype=False)


def test_list_dirs_finds_drop_folders(tmp_path):
    root = storage.join(tmp_path, "landing", "sellin_daily")
    for d in ["2025-01-05", "2024-12-29"]:
        storage.write_csv(pd.DataFrame({"a": [1]}), storage.join(root, f"ingest_date={d}", "part.csv"))
    assert storage.list_dirs(root, "ingest_date=*") == ["ingest_date=2024-12-29", "ingest_date=2025-01-05"]


def test_text_round_trip(tmp_path):
    location = storage.join(tmp_path, "generator", "params.json")
    storage.write_text(location, '{"seed": 42}')
    assert storage.read_text(location) == '{"seed": 42}'
