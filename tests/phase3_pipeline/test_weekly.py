import pandas as pd
import pytest

from demandfcst.pipeline import weekly

SKUS = pd.DataFrame({"sku_id": ["001", "002"], "discontinue_date": pd.to_datetime([None, "2025-01-15"])})


def daily(*rows):
    df = pd.DataFrame(rows, columns=["date", "province", "sku_id", "volume_hl"])
    return df.assign(date=pd.to_datetime(df["date"]))


def weeks_and_volumes(out, sku="001"):
    s = out[out["sku_id"] == sku]
    return [str(w.date()) for w in s["week_start"]], list(s["volume_hl"])


def test_partial_first_and_last_weeks_are_dropped():
    d = daily(("2025-01-03", "SP", "001", 1.0),     # Fri: week of 30 Dec only partly covered
              ("2025-01-06", "SP", "001", 2.0),
              ("2025-01-14", "SP", "001", 3.0),
              ("2025-01-21", "SP", "001", 4.0))     # week of 20 Jan cut off by the end date
    out = weekly.to_weekly(d, SKUS, pd.Timestamp("2025-01-03"), pd.Timestamp("2025-01-22"))
    assert weeks_and_volumes(out) == (["2025-01-06", "2025-01-13"], [2.0, 3.0])


def test_zero_weeks_inside_the_active_life():
    d = daily(("2025-01-06", "SP", "001", 1.0), ("2025-01-20", "SP", "001", 1.0))
    out = weekly.to_weekly(d, SKUS, pd.Timestamp("2025-01-06"), pd.Timestamp("2025-01-26"))
    assert weeks_and_volumes(out) == (["2025-01-06", "2025-01-13", "2025-01-20"], [1.0, 0.0, 1.0])


def test_active_series_runs_to_the_latest_complete_week():
    d = daily(("2025-01-06", "SP", "001", 1.0))                    # no sales in the last two weeks
    out = weekly.to_weekly(d, SKUS, pd.Timestamp("2025-01-06"), pd.Timestamp("2025-01-26"))
    assert weeks_and_volumes(out) == (["2025-01-06", "2025-01-13", "2025-01-20"], [1.0, 0.0, 0.0])


def test_discontinued_sku_stops_at_its_discontinuation_week():
    d = daily(("2025-01-06", "SP", "002", 1.0))                    # 002 discontinued Wed 15 Jan
    out = weekly.to_weekly(d, SKUS, pd.Timestamp("2025-01-06"), pd.Timestamp("2025-01-26"))
    assert weeks_and_volumes(out, sku="002") == (["2025-01-06", "2025-01-13"], [1.0, 0.0])


def test_no_rows_before_the_first_sale():
    d = daily(("2025-01-13", "SP", "001", 1.0))
    out = weekly.to_weekly(d, SKUS, pd.Timestamp("2025-01-06"), pd.Timestamp("2025-01-19"))
    assert weeks_and_volumes(out) == (["2025-01-13"], [1.0])


def test_weekly_total_equals_daily_total():
    d = daily(("2025-01-06", "SP", "001", 1.25), ("2025-01-07", "SP", "001", 2.5),
              ("2025-01-08", "RJ", "001", 4.0))
    out = weekly.to_weekly(d, SKUS, pd.Timestamp("2025-01-06"), pd.Timestamp("2025-01-12"))
    assert out["volume_hl"].sum() == pytest.approx(7.75)


def test_refuses_data_that_was_not_deduplicated():
    d = daily(("2025-01-06", "SP", "001", 1.0), ("2025-01-06", "SP", "001", 1.2))
    with pytest.raises(ValueError, match="deduplicate first"):
        weekly.to_weekly(d, SKUS, pd.Timestamp("2025-01-06"), pd.Timestamp("2025-01-12"))
