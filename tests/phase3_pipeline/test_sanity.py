import pandas as pd

from demandfcst.pipeline import sanity

PROVINCES = pd.DataFrame({"province": ["SP"], "region": ["Sudeste"]})


def flat_history(weeks=60):
    return pd.DataFrame({"province": "SP", "sku_id": "001",
                         "week_start": pd.date_range("2024-01-01", periods=weeks, freq="7D"),
                         "volume_hl": 100.0})


def test_steady_week_passes():
    out = sanity.sanity_checks(flat_history(), PROVINCES)
    assert (out["status"] == "pass").all()


def test_a_doubled_week_is_flagged():
    sw = flat_history()
    sw.loc[sw.index[-1], "volume_hl"] = 200.0
    status = sanity.sanity_checks(sw, PROVINCES).set_index("check")["status"]
    assert status["total_vs_last_week"] == "warning"
    assert status["total_vs_last_year"] == "warning"
    assert status["active_series"] == "pass"
 