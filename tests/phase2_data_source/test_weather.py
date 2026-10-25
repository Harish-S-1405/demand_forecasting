import numpy as np
import pandas as pd
import pytest

from demandfcst.synthetic.weather import f_to_c, load_source_weather, weekly_weather

PROVINCES = pd.DataFrame({"province": ["SP", "RS"]})


def write_fake_source(path):
    """3 years of weekly source-format weather for SP and RS, with one SP week missing."""
    weeks = pd.date_range("2021-01-04", "2023-12-25", freq="7D")
    rows = []
    for prov, base_f in [("SP", 72.0), ("RS", 66.0)]:
        for i, wk in enumerate(weeks):
            temp = base_f + 10 * np.cos(2 * np.pi * i / 52) + (i % 5 - 2)
            rows.append({"Version.[Version Name]": "CurrentWorkingView",
                         "Time.[FiscalWeek]": wk.strftime("%m/%d/%Y"),
                         "Sales Domain.[Province]": prov,
                         "Max Weighted Temp": temp + 8, "Min Weighted Temp": temp - 8,
                         "Weighted Precipitation": 0.3, "Weighted Temperature": temp})
    pd.DataFrame(rows).drop(index=10).to_csv(path, index=False)     # SP week 10 missing
    return weeks


def test_fahrenheit_to_celsius():
    assert f_to_c(32) == 0
    assert f_to_c(212) == pytest.approx(100)


def test_missing_source_week_is_interpolated(tmp_path):
    src = tmp_path / "weather.csv"
    weeks = write_fake_source(src)
    sp = load_source_weather(src, PROVINCES).query("province == 'SP'").set_index("week_start")["temp_avg_c"]
    assert len(sp) == len(weeks)
    assert sp[weeks[10]] == pytest.approx((sp[weeks[9]] + sp[weeks[11]]) / 2)


def test_real_anomalies_average_zero(tmp_path):
    src = tmp_path / "weather.csv"
    write_fake_source(src)
    w = weekly_weather(src, PROVINCES, pd.Timestamp("2021-01-04"), pd.Timestamp("2023-12-31"), seed=42)
    assert w.groupby("province")["anomaly_c"].mean().abs().max() < 0.05


def test_weeks_after_source_are_synthetic_and_reproducible(tmp_path):
    src = tmp_path / "weather.csv"
    write_fake_source(src)                                          # source ends 2023-12-25
    full = weekly_weather(src, PROVINCES, pd.Timestamp("2023-12-18"), pd.Timestamp("2024-01-21"), seed=42)
    assert not full.loc[full["week_start"] <= "2023-12-25", "is_synthetic"].any()
    assert full.loc[full["week_start"] > "2023-12-25", "is_synthetic"].all()

    alone = weekly_weather(src, PROVINCES, pd.Timestamp("2024-01-08"), pd.Timestamp("2024-01-14"), seed=42)
    both = alone.merge(full, on=["province", "week_start"], suffixes=("_alone", "_full"))
    assert len(both) == 2
    assert np.allclose(both["temp_avg_c_alone"], both["temp_avg_c_full"])
