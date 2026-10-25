from types import SimpleNamespace

import pandas as pd
import pytest

from demandfcst import drops, storage

W1, W2, W3 = pd.Timestamp("2025-01-05"), pd.Timestamp("2025-01-12"), pd.Timestamp("2025-01-19")
SALES_COLS = ["date", "province", "sku_id", "volume_hl"]
WEATHER_COLS = ["province", "week_start", "temp_max_c", "temp_min_c", "temp_avg_c", "precipitation"]


def put(raw, dataset, ingest_date, rows, columns):
    """Write one complete raw drop."""
    storage.write_csv(pd.DataFrame(rows, columns=columns),
                      storage.join(drops.drop_dir(raw, dataset, ingest_date), "part.csv"))
    drops.mark_complete(raw, dataset, ingest_date)


@pytest.fixture
def small_raw(tmp_path):
    """A tiny raw area: 2 weekly deliveries, 2 provinces, 2 SKUs. Plus a processed path."""
    raw = storage.join(tmp_path, "raw")
    put(raw, "province_master", W1, [("SP", "São Paulo", "Sudeste"), ("RJ", "Rio de Janeiro", "Sudeste")],
        ["province", "province_name", "region"])
    put(raw, "sku_master", W1, [("001", "A CAN", "A", "LATA 350ML", "can", 350, 12, False, "", ""),
                                ("002", "B CAN", "B", "LATA 350ML", "can", 350, 12, False, "", "")],
        ["sku_id", "sku_name", "brand", "pack", "container", "size_ml", "units_per_case", "returnable",
         "launch_date", "discontinue_date"])
    put(raw, "holidays", W1, [("2025-01-01", "BR", "Confraternização Universal")],
        ["date", "province", "holiday_name"])
    put(raw, "sellin_daily", W1, [("2024-12-31", "SP", "001", 1.5), ("2025-01-02", "SP", "001", 2.5)], SALES_COLS)
    put(raw, "sellin_daily", W2, [("2025-01-07", "SP", "001", 3.0)], SALES_COLS)
    for ingest, week in [(W1, "2024-12-30"), (W2, "2025-01-06")]:
        put(raw, "weather_weekly", ingest, [("SP", week, 30, 20, 25, 1.0), ("RJ", week, 30, 20, 25, 1.0)],
            WEATHER_COLS)
    return SimpleNamespace(raw=raw, processed=storage.join(tmp_path, "processed"),
                           start=pd.Timestamp("2024-12-30"), put=put)
