"""What exists in the synthetic market: provinces, SKUs and per-series settings.

build_catalog(seed) draws every series' settings once. save_params() stores them in
generator_params.json, so later runs (e.g. the weekly release) reuse exactly the same
series and settings instead of drawing new ones.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

# --- Geography: 9 placeholder states; size = relative market size (SP = 1.0) ----------
PROVINCES = [
    ("SP", "São Paulo", "Sudeste", 1.00),
    ("RJ", "Rio de Janeiro", "Sudeste", 0.40),
    ("MG", "Minas Gerais", "Sudeste", 0.45),
    ("RS", "Rio Grande do Sul", "Sul", 0.30),
    ("PR", "Paraná", "Sul", 0.28),
    ("SC", "Santa Catarina", "Sul", 0.18),
    ("BA", "Bahia", "Nordeste", 0.30),
    ("PE", "Pernambuco", "Nordeste", 0.20),
    ("CE", "Ceará", "Nordeste", 0.18),
]

# --- Products: popularity = brand popularity x pack popularity ------------------------
BRANDS = {
    "BRAHMA": 1.0, "SKOL": 0.9, "ANTARCTICA": 0.6, "BUDWEISER": 0.5,
    "ORIGINAL": 0.4, "STELLA ARTOIS": 0.3, "CORONA": 0.3, "SPATEN": 0.25,
}
PACKS = [  # pack, container, size_ml, units_per_case, returnable, popularity
    ("LATA 269ML", "can", 269, 15, False, 0.7),
    ("LATA 350ML", "can", 350, 12, False, 1.0),
    ("LATA 473ML", "can", 473, 12, False, 0.6),
    ("LONG NECK 330ML", "bottle", 330, 24, False, 0.4),
    ("GARRAFA 600ML", "bottle", 600, 24, True, 0.8),
    ("BARRIL 30L", "keg", 30000, 1, True, 0.3),
]
N_SKUS = 40
PREMIUM_BRANDS = {"STELLA ARTOIS", "CORONA", "SPATEN", "BUDWEISER"}
PROMO_BRANDS = {"BRAHMA", "SKOL", "ANTARCTICA", "BUDWEISER", "ORIGINAL"}
LAUNCH_DATES = ["2022-03-07", "2022-10-03", "2023-06-05", "2024-04-01"]       # Mondays
DISCONTINUE_DATES = ["2022-12-25", "2023-08-27", "2024-06-30"]                # Sundays

# --- Series settings ---------------------------------------------------------------------
CORE_POPULARITY = 0.5               # core SKUs are sold in every province
SCALE_HL = 1200                     # SP x best seller ~ 1,200 HL/week
NORDESTE_600ML_TASTE = 1.5
BASE_NOISE_SIGMA = 0.4
TREND_PREMIUM = 0.05
TREND_SD = 0.03
SEASON_AMP = {"Sul": 0.35, "Sudeste": 0.25, "Nordeste": 0.10}
WEATHER_BETA_RANGE = (0.02, 0.04)   # +2-4% per degree C above normal
PROMO_SHARE = 0.7                   # share of promo-brand series that run promotions
PROMO_RATE_RANGE = (1 / 14, 1 / 7)  # chance a week is a promotion week
SPARSE_QUANTILE = 0.15              # smallest 15% of series are sparse
SPARSE_KEG_SHARE = 0.3              # plus some kegs
ORDER_PROB_RANGE = (0.3, 0.7)       # sparse: chance a week has an order
SPARSE_CV = {"intermittent": 0.3, "lumpy": 1.0}
ERRATIC_SHARE = 0.15                # of the smaller dense series
ERRATIC_WEEK_CV = 0.9               # week-to-week size variation for erratic series

DATE_COLUMNS = {"skus": ["launch_date", "discontinue_date"]}


def build_provinces():
    return pd.DataFrame(PROVINCES, columns=["province", "province_name", "region", "size"])


def build_skus(rng):
    """40 SKUs drawn from all brand x pack combinations, with codes and lifecycle dates."""
    combos = pd.DataFrame([
        {"brand": brand, "pack": pack, "container": container, "size_ml": size_ml,
         "units_per_case": upc, "returnable": returnable, "popularity": round(b_pop * p_pop, 3)}
        for brand, b_pop in BRANDS.items()
        for pack, container, size_ml, upc, returnable, p_pop in PACKS
    ])
    keep = rng.choice(len(combos), size=N_SKUS, replace=False)
    skus = combos.iloc[np.sort(keep)].reset_index(drop=True)

    codes = rng.choice(np.arange(10000, 100000), size=N_SKUS, replace=False)
    skus.insert(0, "sku_id", codes.astype(str))                      # text, per the contract
    skus.insert(1, "sku_name", skus["brand"] + " " + skus["pack"])

    skus["launch_date"] = pd.NaT
    skus["discontinue_date"] = pd.NaT
    picked = rng.choice(N_SKUS, size=len(LAUNCH_DATES) + len(DISCONTINUE_DATES), replace=False)
    launch_idx, disc_idx = picked[:len(LAUNCH_DATES)], picked[len(LAUNCH_DATES):]
    skus.loc[launch_idx, "launch_date"] = pd.to_datetime(LAUNCH_DATES)
    skus.loc[disc_idx, "discontinue_date"] = pd.to_datetime(DISCONTINUE_DATES)
    return skus


def build_series(provinces, skus, rng):
    """Active province x SKU pairs and every series' generator settings."""
    series = provinces[["province", "region", "size"]].merge(
        skus[["sku_id", "brand", "pack", "container", "popularity"]], how="cross")

    # which pairs are sold: core SKUs everywhere, others more likely in big states
    core = series["popularity"] >= CORE_POPULARITY
    p_sell = (0.35 + 0.6 * series["size"]).clip(upper=0.95)
    series = series[core | (rng.random(len(series)) < p_sell)].reset_index(drop=True)
    n = len(series)

    taste = np.where((series["region"] == "Nordeste") & (series["pack"] == "GARRAFA 600ML"),
                     NORDESTE_600ML_TASTE, 1.0)
    noise = rng.lognormal(0.0, BASE_NOISE_SIGMA, n)
    series["base_hl_week"] = (SCALE_HL * series["size"] * series["popularity"] * taste * noise).round(1)

    drift = np.where(series["brand"].isin(PREMIUM_BRANDS), TREND_PREMIUM, 0.0)
    series["trend_per_year"] = (drift + rng.normal(0.0, TREND_SD, n)).round(3)
    series["season_amp"] = (series["region"].map(SEASON_AMP) * rng.uniform(0.8, 1.2, n)).round(3)
    series["weather_beta"] = rng.uniform(*WEATHER_BETA_RANGE, n).round(3)

    has_promo = series["brand"].isin(PROMO_BRANDS) & (rng.random(n) < PROMO_SHARE)
    series["promo_rate"] = np.where(has_promo, rng.uniform(*PROMO_RATE_RANGE, n), 0.0).round(3)

    # demand type: sparse (intermittent / lumpy), erratic, or smooth
    small = series["base_hl_week"] <= series["base_hl_week"].quantile(SPARSE_QUANTILE)
    keg = (series["container"] == "keg") & (rng.random(n) < SPARSE_KEG_SHARE)
    sparse = small | keg
    lumpy = rng.random(n) < 0.5
    erratic = (~sparse & (series["base_hl_week"] < series["base_hl_week"].median())
               & (rng.random(n) < ERRATIC_SHARE))
    series["designed_segment"] = np.select(
        [sparse & lumpy, sparse, erratic], ["lumpy", "intermittent", "erratic"], default="smooth")

    series["order_prob"] = np.where(sparse, rng.uniform(*ORDER_PROB_RANGE, n), 1.0).round(2)
    series["noise_cv"] = np.where(
        sparse,
        np.where(lumpy, SPARSE_CV["lumpy"], SPARSE_CV["intermittent"]),
        (0.25 + 3 / np.sqrt(series["base_hl_week"])).clip(upper=0.8),
    ).round(2)
    series["week_cv"] = np.where(erratic, ERRATIC_WEEK_CV, 0.0)

    series.insert(0, "series_num", np.arange(n))                     # permanent id for seeding
    return series.drop(columns=["region", "size", "brand", "pack", "container", "popularity"])


def build_catalog(seed):
    """Provinces, SKUs and series settings, fully determined by the seed."""
    rng = np.random.default_rng(seed)
    provinces = build_provinces()
    skus = build_skus(rng)
    series = build_series(provinces, skus, rng)
    return {"provinces": provinces, "skus": skus, "series": series}


def save_params(catalog, path, *, seed, history_start, history_end):
    """Write the catalog and run settings to a JSON file (UTF-8, no BOM)."""
    params = {"seed": seed,
              "history_start": str(history_start.date()),
              "history_end": str(history_end.date())}
    for name, df in catalog.items():
        out = df.copy()
        for col in DATE_COLUMNS.get(name, []):
            out[col] = out[col].dt.strftime("%Y-%m-%d")              # NaT -> null
        params[name] = json.loads(out.to_json(orient="records", force_ascii=False))

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(params, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_params(path):
    """Read generator_params.json back into DataFrames. Returns (catalog, meta)."""
    params = json.loads(Path(path).read_text(encoding="utf-8"))
    catalog = {name: pd.DataFrame(params[name]) for name in ("provinces", "skus", "series")}
    for name, cols in DATE_COLUMNS.items():
        for col in cols:
            catalog[name][col] = pd.to_datetime(catalog[name][col])
    for name in ("skus", "series"):
        catalog[name]["sku_id"] = catalog[name]["sku_id"].astype(str)
    meta = {k: params[k] for k in ("seed", "history_start", "history_end")}
    return catalog, meta
