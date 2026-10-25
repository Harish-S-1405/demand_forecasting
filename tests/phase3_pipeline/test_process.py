import json

import pandas as pd
import pytest

from demandfcst import drops, storage
from demandfcst.pipeline import process, validate

W1, W2, W3 = pd.Timestamp("2025-01-05"), pd.Timestamp("2025-01-12"), pd.Timestamp("2025-01-19")
START = pd.Timestamp("2024-12-30")


def put(raw, dataset, ingest_date, rows, columns):
    df = pd.DataFrame(rows, columns=columns)
    storage.write_csv(df, storage.join(drops.drop_dir(raw, dataset, ingest_date), "part.csv"))
    drops.mark_complete(raw, dataset, ingest_date)


def make_raw(tmp_path):
    raw = storage.join(tmp_path, "raw")
    put(raw, "province_master", W1, [("SP", "São Paulo", "Sudeste"), ("RJ", "Rio de Janeiro", "Sudeste")],
        ["province", "province_name", "region"])
    put(raw, "sku_master", W1, [("001", "A CAN", "A", "LATA 350ML", "can", 350, 12, False, "", ""),
                                ("002", "B CAN", "B", "LATA 350ML", "can", 350, 12, False, "", "")],
        ["sku_id", "sku_name", "brand", "pack", "container", "size_ml", "units_per_case", "returnable",
         "launch_date", "discontinue_date"])
    put(raw, "holidays", W1, [("2025-01-01", "BR", "Confraternização Universal")],
        ["date", "province", "holiday_name"])
    sales_cols = ["date", "province", "sku_id", "volume_hl"]
    put(raw, "sellin_daily", W1, [("2024-12-31", "SP", "001", 1.5), ("2025-01-02", "SP", "001", 2.5)], sales_cols)
    put(raw, "sellin_daily", W2, [("2025-01-07", "SP", "001", 3.0)], sales_cols)
    wx_cols = ["province", "week_start", "temp_max_c", "temp_min_c", "temp_avg_c", "precipitation"]
    for ingest, week in [(W1, "2024-12-30"), (W2, "2025-01-06")]:
        put(raw, "weather_weekly", ingest, [("SP", week, 30, 20, 25, 1.0), ("RJ", week, 30, 20, 25, 1.0)], wx_cols)
    return raw, storage.join(tmp_path, "processed")


def test_run_writes_parquet_csv_info_and_marker(tmp_path):
    raw, processed = make_raw(tmp_path)
    outputs, info = process.run(raw, processed, START)
    for name in outputs:
        assert storage.exists(storage.join(processed, f"{name}.parquet"))
        assert storage.exists(storage.join(processed, "csv", f"{name}.csv"))
    assert storage.exists(storage.join(processed, drops.SUCCESS))
    assert json.loads(storage.read_text(storage.join(processed, "run_info.json")))["weeks"] == 2
    assert not storage.exists(processed + "_staging")                       # swapped in, nothing left over


def test_weekly_parquet_keeps_values_and_types(tmp_path):
    raw, processed = make_raw(tmp_path)
    process.run(raw, processed, START)
    sw = pd.read_parquet(storage.join(processed, "sales_weekly.parquet"))
    assert list(sw["week_start"].dt.strftime("%Y-%m-%d")) == ["2024-12-30", "2025-01-06"]
    assert list(sw["volume_hl"]) == [4.0, 3.0]                              # 1.5 + 2.5, then 3.0
    assert sw["sku_id"].iloc[0] == "001"                                    # text, leading zeros kept


def test_errors_stop_the_run_and_keep_previous_outputs(tmp_path):
    raw, processed = make_raw(tmp_path)
    process.run(raw, processed, START)                                      # a good first run
    put(raw, "sellin_daily", W3, [("2025-01-14", "SP", "001", 0.0)],        # bad delivery: zero volume
        ["date", "province", "sku_id", "volume_hl"])
    with pytest.raises(validate.ValidationError, match="volume_not_positive"):
        process.run(raw, processed, START)
    sw = pd.read_parquet(storage.join(processed, "sales_weekly.parquet"))
    assert sw["week_start"].max() == pd.Timestamp("2025-01-06")             # previous outputs untouched
