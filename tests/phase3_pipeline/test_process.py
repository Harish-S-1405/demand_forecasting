import json

import pandas as pd
import pytest

from conftest import SALES_COLS, W3
from demandfcst import drops, storage
from demandfcst.pipeline import process, validate


def test_run_writes_parquet_csv_info_and_marker(small_raw):
    outputs, info = process.run(small_raw.raw, small_raw.processed, small_raw.start)
    for name in outputs:
        assert storage.exists(storage.join(small_raw.processed, f"{name}.parquet"))
        assert storage.exists(storage.join(small_raw.processed, "csv", f"{name}.csv"))
    assert storage.exists(storage.join(small_raw.processed, drops.SUCCESS))
    assert json.loads(storage.read_text(storage.join(small_raw.processed, "run_info.json")))["weeks"] == 2
    assert not storage.exists(small_raw.processed + "_staging")


def test_weekly_parquet_keeps_values_and_types(small_raw):
    process.run(small_raw.raw, small_raw.processed, small_raw.start)
    sw = pd.read_parquet(storage.join(small_raw.processed, "sales_weekly.parquet"))
    assert list(sw["week_start"].dt.strftime("%Y-%m-%d")) == ["2024-12-30", "2025-01-06"]
    assert list(sw["volume_hl"]) == [4.0, 3.0]
    assert sw["sku_id"].iloc[0] == "001"


def test_errors_stop_the_run_and_keep_previous_outputs(small_raw):
    process.run(small_raw.raw, small_raw.processed, small_raw.start)
    small_raw.put(small_raw.raw, "sellin_daily", W3, [("2025-01-14", "SP", "001", 0.0)], SALES_COLS)
    with pytest.raises(validate.ValidationError, match="volume_not_positive"):
        process.run(small_raw.raw, small_raw.processed, small_raw.start)
    sw = pd.read_parquet(storage.join(small_raw.processed, "sales_weekly.parquet"))
    assert sw["week_start"].max() == pd.Timestamp("2025-01-06")
