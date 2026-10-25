import pandas as pd

from demandfcst.pipeline import dedupe

KEY = ["province", "sku_id", "date"]
W1, W2 = pd.Timestamp("2025-01-05"), pd.Timestamp("2025-01-12")
D1, D2 = pd.Timestamp("2025-01-02"), pd.Timestamp("2025-01-03")


def deliveries():
    return pd.DataFrame({"date": [D1, D2, D1], "province": ["SP"] * 3, "sku_id": ["001"] * 3,
                         "volume_hl": [1.0, 2.0, 1.5], "ingest_date": [W1, W1, W2]})   # D1 corrected in W2


def test_latest_drop_wins():
    current, superseded = dedupe.latest_wins(deliveries(), KEY)
    assert len(current) == 2
    assert current.loc[current["date"] == D1, "volume_hl"].item() == 1.5
    assert superseded[["date", "volume_hl"]].values.tolist() == [[D1, 1.0]]


def test_restatement_summary_shows_the_change():
    current, superseded = dedupe.latest_wins(deliveries(), KEY)
    summary = dedupe.restatement_summary(current, superseded, KEY)
    assert summary.to_dict("records") == [
        {"ingest_date": W2, "restated_days": 1, "hl_before": 1.0, "hl_after": 1.5, "hl_change": 0.5}]


def test_no_restatements_gives_an_empty_summary():
    current, superseded = dedupe.latest_wins(deliveries().iloc[:2], KEY)
    assert superseded.empty
    assert dedupe.restatement_summary(current, superseded, KEY).empty
