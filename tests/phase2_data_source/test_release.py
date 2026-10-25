import pandas as pd
import pytest

from demandfcst import storage
from demandfcst.synthetic import catalog, demand, landing, release, weather,corrections

SEED = 42
HISTORY_END = pd.Timestamp("2024-12-29")


@pytest.fixture
def setup(tmp_path, fake_weather_source):
    """A landing area whose latest complete sales drop ends 2024-12-29, plus saved params."""
    cat = catalog.build_catalog(SEED)
    params = catalog.save_params(cat, tmp_path / "params.json", seed=SEED,
                                 history_start=pd.Timestamp("2021-01-01"), history_end=HISTORY_END)
    landing_root, truth_root = tmp_path / "landing", tmp_path / "truth"
    landing.write_drop(pd.DataFrame(columns=["date", "province", "sku_id", "volume_hl"]),
                       landing_root, "sellin_daily", HISTORY_END)
    landing.mark_complete(landing_root, "sellin_daily", HISTORY_END)
    return {"cat": cat, "params": params, "landing": landing_root, "truth": truth_root,
            "source": fake_weather_source}


def run(s):
    return release.release_next_week(s["landing"], s["truth"], s["params"], s["source"])


def read_sales(root, ingest):
    return pd.read_csv(storage.join(landing.drop_dir(root, "sellin_daily", ingest), "part.csv"),
                       dtype={"province": str, "sku_id": str}, parse_dates=["date"])


def test_next_week_follows_a_sunday():
    assert release.next_week(pd.Timestamp("2024-12-29")) == (pd.Timestamp("2024-12-30"),
                                                              pd.Timestamp("2025-01-05"))
    with pytest.raises(ValueError):
        release.next_week(pd.Timestamp("2024-12-31"))


def test_each_run_appends_the_next_week(setup):
    assert run(setup) == pd.Timestamp("2025-01-05")
    assert run(setup) == pd.Timestamp("2025-01-12")
    assert release.drop_dates(setup["landing"], "sellin_daily") == [
        pd.Timestamp("2024-12-29"), pd.Timestamp("2025-01-05"), pd.Timestamp("2025-01-12")]

    sales = read_sales(setup["landing"], pd.Timestamp("2025-01-05"))
    assert len(sales) > 0
    assert sales["date"].between("2024-12-30", "2025-01-05").all()
    wx = pd.read_csv(storage.join(landing.drop_dir(setup["landing"], "weather_weekly",
                                                   pd.Timestamp("2025-01-05")), "part.csv"))
    assert len(wx) == 9


def test_released_week_matches_a_continuous_generation(setup):
    run(setup)
    released = read_sales(setup["landing"], pd.Timestamp("2025-01-05"))

    start, end = pd.Timestamp("2024-12-16"), pd.Timestamp("2025-01-12")
    wx = weather.weekly_weather(setup["source"], setup["cat"]["provinces"], start, end, SEED)
    continuous, _ = demand.generate_daily(start, end, setup["cat"], wx, SEED)
    week = continuous[continuous["date"].between("2024-12-30", "2025-01-05")].reset_index(drop=True)
    pd.testing.assert_frame_equal(released, week, check_dtype=False)


def test_release_works_on_an_object_store(tmp_path, fake_weather_source):
    root = f"memory://{tmp_path.name}"                     # unique per test: memory:// is shared in-process
    cat = catalog.build_catalog(SEED)
    params = catalog.save_params(cat, f"{root}/generator/generator_params.json", seed=SEED,
                                 history_start=pd.Timestamp("2021-01-01"), history_end=HISTORY_END)
    landing.write_drop(pd.DataFrame(columns=["date", "province", "sku_id", "volume_hl"]),
                       f"{root}/landing", "sellin_daily", HISTORY_END)
    landing.mark_complete(f"{root}/landing", "sellin_daily", HISTORY_END)

    assert release.release_next_week(f"{root}/landing", f"{root}/truth", params,
                                     fake_weather_source) == pd.Timestamp("2025-01-05")
    assert len(read_sales(f"{root}/landing", pd.Timestamp("2025-01-05"))) > 0


def test_crashed_release_is_redone(setup):
    crashed = pd.Timestamp("2025-01-05")
    landing.write_drop(pd.DataFrame({"junk": [1]}), setup["landing"], "sellin_daily", crashed)  # no marker
    assert run(setup) == crashed                          # the same week is released again
    sales = read_sales(setup["landing"], crashed)
    assert "volume_hl" in sales.columns and len(sales) > 0
    assert landing.is_complete(setup["landing"], "sellin_daily", crashed)

def test_correction_rows_restate_real_earlier_days(setup):
    ingest = release.release_next_week(setup["landing"], setup["truth"], setup["params"],
                                       setup["source"], correction_prob=1.0)
    sales = read_sales(setup["landing"], ingest)
    week_start = ingest - pd.Timedelta(days=6)
    restated = sales[sales["date"] < week_start]
    assert 1 <= len(restated) <= corrections.MAX_ROWS

    start = week_start - pd.Timedelta(weeks=corrections.LOOKBACK_WEEKS)
    wx = weather.weekly_weather(setup["source"], setup["cat"]["provinces"], start, ingest, SEED)
    original, _ = demand.generate_daily(start, week_start - pd.Timedelta(days=1), setup["cat"], wx, SEED)
    both = restated.merge(original, on=["date", "province", "sku_id"], suffixes=("_new", "_old"))
    assert len(both) == len(restated)                          # every correction targets a delivered day
    assert (both["volume_hl_new"] != both["volume_hl_old"]).any()
    assert landing.is_complete(setup["truth"], "corrections", ingest)
