import pandas as pd

from demandfcst.synthetic.catalog import build_catalog, load_params, save_params

SEED = 42


def test_same_seed_gives_same_catalog():
    a, b = build_catalog(SEED), build_catalog(SEED)
    for name in ("provinces", "skus", "series"):
        pd.testing.assert_frame_equal(a[name], b[name])


def test_sku_ids_are_unique_text():
    skus = build_catalog(SEED)["skus"]
    assert skus["sku_id"].is_unique
    assert skus["sku_id"].map(type).eq(str).all()


def test_core_skus_sold_in_every_province():
    cat = build_catalog(SEED)
    core = cat["skus"].loc[cat["skus"]["popularity"] >= 0.5, "sku_id"]
    sold = cat["series"][cat["series"]["sku_id"].isin(core)]
    assert set(sold["sku_id"]) == set(core)
    assert (sold.groupby("sku_id")["province"].nunique() == 9).all()


def test_all_four_segments_designed():
    segments = set(build_catalog(SEED)["series"]["designed_segment"])
    assert segments == {"smooth", "erratic", "intermittent", "lumpy"}


def test_segment_settings_are_consistent():
    s = build_catalog(SEED)["series"]
    sparse = s["designed_segment"].isin(["intermittent", "lumpy"])
    erratic = s["designed_segment"] == "erratic"
    assert (s.loc[sparse, "order_prob"] < 1).all()
    assert (s.loc[~sparse, "order_prob"] == 1).all()
    assert (s.loc[erratic, "week_cv"] > 0).all()
    assert (s.loc[~erratic, "week_cv"] == 0).all()


def test_params_round_trip(tmp_path):
    cat = build_catalog(SEED)
    path = save_params(cat, tmp_path / "params.json", seed=SEED,
                       history_start=pd.Timestamp("2021-01-01"),
                       history_end=pd.Timestamp("2024-12-29"))
    loaded, meta = load_params(path)

    assert meta == {"seed": SEED, "history_start": "2021-01-01", "history_end": "2024-12-29"}
    pd.testing.assert_frame_equal(loaded["series"], cat["series"], check_dtype=False)

    dates = ["launch_date", "discontinue_date"]
    pd.testing.assert_frame_equal(loaded["skus"].drop(columns=dates),
                                  cat["skus"].drop(columns=dates), check_dtype=False)
    for col in dates:
        a, b = loaded["skus"][col], cat["skus"][col]
        assert ((a == b) | (a.isna() & b.isna())).all()
