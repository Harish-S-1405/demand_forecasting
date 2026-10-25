import pandas as pd
import pytest

from demandfcst.pipeline import validate

W1, W2 = pd.Timestamp("2025-01-05"), pd.Timestamp("2025-01-12")


def clean():
    """Two provinces, two SKUs, two weekly drops: valid by every rule."""
    provinces = pd.DataFrame({"province": ["SP", "RJ"], "province_name": ["São Paulo", "Rio de Janeiro"],
                              "region": ["Sudeste", "Sudeste"]})
    skus = pd.DataFrame({"sku_id": ["001", "002"], "sku_name": ["A CAN", "B CAN"], "brand": ["A", "B"],
                         "pack": ["LATA 350ML"] * 2, "container": ["can"] * 2,
                         "size_ml": pd.array([350, 350], dtype="Int64"),
                         "units_per_case": pd.array([12, 12], dtype="Int64"),
                         "returnable": pd.array([False, False], dtype="boolean"),
                         "launch_date": pd.to_datetime([None, None]),
                         "discontinue_date": pd.to_datetime([None, None])})
    holidays = pd.DataFrame({"date": pd.to_datetime(["2025-01-01"]), "province": ["BR"],
                             "holiday_name": ["Confraternização Universal"]})
    sales = pd.DataFrame({"date": pd.to_datetime(["2025-01-02", "2025-01-09"]), "province": ["SP", "SP"],
                          "sku_id": ["001", "001"], "volume_hl": [1.0, 2.0], "ingest_date": [W1, W2]})
    weeks = list(pd.to_datetime(["2024-12-30", "2025-01-06"]))
    weather = pd.DataFrame({"province": ["SP", "SP", "RJ", "RJ"], "week_start": weeks * 2,
                            "temp_max_c": 30.0, "temp_min_c": 20.0, "temp_avg_c": 25.0,
                            "precipitation": 1.0, "ingest_date": [W1, W2, W1, W2]})
    return {"province_master": provinces, "sku_master": skus, "holidays": holidays,
            "sellin_daily": sales, "weather_weekly": weather}


def dup_in_drop(t):
    t["sellin_daily"] = pd.concat([t["sellin_daily"], t["sellin_daily"].iloc[[0]]], ignore_index=True)


def zero_volume(t):
    t["sellin_daily"].loc[0, "volume_hl"] = 0.0


def unknown_sku(t):
    t["sellin_daily"].loc[0, "sku_id"] = "999"


def future_date(t):
    t["sellin_daily"].loc[1, "date"] = pd.Timestamp("2025-01-20")


def missing_drop(t):
    t["sellin_daily"].loc[1, "date"] = pd.Timestamp("2025-01-16")
    t["sellin_daily"].loc[1, "ingest_date"] = pd.Timestamp("2025-01-19")      # the 2025-01-12 drop never came


def missing_weather(t):
    t["weather_weekly"] = t["weather_weekly"].iloc[1:]


def bad_temps(t):
    t["weather_weekly"].loc[0, "temp_min_c"] = 35.0                          # min above max


def backwards_lifecycle(t):
    t["sku_master"].loc[0, "launch_date"] = pd.Timestamp("2025-02-01")
    t["sku_master"].loc[0, "discontinue_date"] = pd.Timestamp("2025-01-01")


def test_clean_tables_pass_every_check():
    report = validate.validate(clean())
    assert validate.problems(report).empty
    assert (report["level"] == "pass").all()


def test_every_check_is_listed_even_when_it_passes():
    checks = set(validate.validate(clean())["check"])
    assert {"duplicate_in_drop", "missing_drop", "missing_weather_week", "sales_without_weather"} <= checks
    assert len(checks) >= 20


def test_restatement_is_info_not_a_warning_or_error():
    tables = clean()
    correction = tables["sellin_daily"].iloc[[0]].assign(volume_hl=1.2, ingest_date=W2)
    tables["sellin_daily"] = pd.concat([tables["sellin_daily"], correction], ignore_index=True)
    found = validate.problems(validate.validate(tables))
    assert list(found["check"]) == ["restated_rows"]
    assert (found["level"] == "info").all()



@pytest.mark.parametrize("break_it, check", [
    (dup_in_drop, "duplicate_in_drop"),
    (zero_volume, "volume_not_positive"),
    (unknown_sku, "unknown_sku"),
    (future_date, "date_after_ingest"),
    (missing_drop, "missing_drop"),
    (missing_weather, "missing_weather_week"),
    (bad_temps, "temperature_order"),
    (backwards_lifecycle, "lifecycle_dates"),
])
def test_each_rule_catches_its_problem(break_it, check):
    tables = clean()
    break_it(tables)
    report = validate.validate(tables)
    assert check in set(report.loc[report["level"] == "error", "check"])




def test_errors_stop_the_pipeline_warnings_do_not():
    validate.raise_if_errors(validate.validate(clean()))                     # clean: no exception
    tables = clean()
    zero_volume(tables)
    with pytest.raises(validate.ValidationError, match="volume_not_positive"):
        validate.raise_if_errors(validate.validate(tables))
