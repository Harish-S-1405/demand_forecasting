import pandas as pd

from demandfcst.synthetic.catalog import build_catalog
from demandfcst.synthetic.demand import generate_daily

SEED = 42
CATALOG = build_catalog(SEED)


def flat_weather(start, end):
    """Normal weather (anomaly 0) for every province and week touching start..end."""
    weeks = pd.date_range(start - pd.Timedelta(days=start.day_of_week), end, freq="7D")
    return (CATALOG["provinces"][["province"]]
            .merge(pd.DataFrame({"week_start": weeks}), how="cross")
            .assign(anomaly_c=0.0))


def generate(start, end):
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    return generate_daily(start, end, CATALOG, flat_weather(start, end), SEED)


def test_week_alone_matches_same_week_in_longer_range():
    full, _ = generate("2024-11-04", "2024-12-29")
    alone, _ = generate("2024-12-16", "2024-12-22")
    week = full[(full["date"] >= "2024-12-16") & (full["date"] <= "2024-12-22")].reset_index(drop=True)
    assert len(alone) > 0
    pd.testing.assert_frame_equal(alone, week)


def test_output_follows_the_contract():
    sales, _ = generate("2024-03-01", "2024-04-30")
    assert list(sales.columns) == ["date", "province", "sku_id", "volume_hl"]
    assert (sales["volume_hl"] > 0).all()
    assert not sales.duplicated(["province", "sku_id", "date"]).any()
    assert sales["date"].between("2024-03-01", "2024-04-30").all()
    assert (sales["date"].dt.day_of_week != 6).all()


def test_no_sales_before_launch_or_after_discontinuation():
    skus = CATALOG["skus"]
    launched = skus.dropna(subset=["launch_date"]).sort_values("popularity").iloc[-1]
    stopped = skus.dropna(subset=["discontinue_date"]).sort_values("popularity").iloc[-1]

    launch = launched["launch_date"]
    sales, _ = generate(launch - pd.Timedelta(weeks=4), launch + pd.Timedelta(weeks=4))
    rows = sales[sales["sku_id"] == launched["sku_id"]]
    assert len(rows) > 0 and (rows["date"] >= launch).all()

    stop = stopped["discontinue_date"]
    sales, _ = generate(stop - pd.Timedelta(weeks=4), stop + pd.Timedelta(weeks=4))
    rows = sales[sales["sku_id"] == stopped["sku_id"]]
    assert len(rows) > 0 and (rows["date"] <= stop).all()


def test_sparse_series_deliver_at_most_one_day_per_week():
    sales, _ = generate("2024-01-01", "2024-03-31")
    series = CATALOG["series"]
    sparse = series.loc[series["order_prob"] < 1, ["province", "sku_id"]]
    s = sales.merge(sparse, on=["province", "sku_id"])
    wk = s["date"] - pd.to_timedelta(s["date"].dt.day_of_week, unit="D")
    assert len(s) > 0
    assert s.groupby(["province", "sku_id", wk]).size().max() == 1
