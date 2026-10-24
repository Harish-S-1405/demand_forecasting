"""Weekly weather per province for the synthetic generator.

Real temperatures come from the source file (weekly, degrees F, o9-style columns).
Weeks the source doesn't cover get synthetic weather: the climate normal for that
province and week of year plus a random anomaly, seeded per (province, week), so any
week is generated identically whether alone or as part of a long range.
"""

import numpy as np
import pandas as pd

from demandfcst.synthetic.calendar import week_number

SOURCE_COLUMNS = {
    "Sales Domain.[Province]": "province",
    "Time.[FiscalWeek]": "week_start",
    "Max Weighted Temp": "temp_max_f",
    "Min Weighted Temp": "temp_min_f",
    "Weighted Temperature": "temp_avg_f",
    "Weighted Precipitation": "precipitation",
}
SOURCE_DATE_FORMAT = "%m/%d/%Y"
WEATHER_COLUMNS = ["province", "week_start", "temp_max_c", "temp_min_c", "temp_avg_c", "precipitation"]
NORMAL_COLUMNS = ["temp_max_c", "temp_min_c", "temp_avg_c", "precipitation"]
SEED_STREAM = 1                     # keeps weather randomness separate from demand's


def f_to_c(f):
    return (f - 32) * 5 / 9


def week_of_year(dates):
    """ISO week of year; week 53 is merged into week 52."""
    return dates.dt.isocalendar().week.astype(int).clip(upper=52)


def province_key(code):
    """Stable integer for a province code (e.g. "SP" -> 21328), used in random seeds."""
    return int.from_bytes(code.encode("utf-8"), "big")


def load_source_weather(path, provinces):
    """Real weekly weather for our provinces, in contract columns, with gaps interpolated."""
    raw = pd.read_csv(path).rename(columns=SOURCE_COLUMNS)
    w = raw[raw["province"].isin(provinces["province"])].copy()
    w["week_start"] = pd.to_datetime(w["week_start"], format=SOURCE_DATE_FORMAT)
    for t in ["max", "min", "avg"]:
        w[f"temp_{t}_c"] = f_to_c(w[f"temp_{t}_f"]).round(2)
    w = w[WEATHER_COLUMNS]

    if w.duplicated(["province", "week_start"]).any():
        raise ValueError("source weather has duplicate province-weeks")
    if not (w["week_start"].dt.day_of_week == 0).all():
        raise ValueError("source weather has week labels that are not Mondays")

    all_weeks = pd.date_range(w["week_start"].min(), w["week_start"].max(), freq="7D")
    full = pd.MultiIndex.from_product([provinces["province"], all_weeks],
                                      names=["province", "week_start"])
    w = (w.set_index(["province", "week_start"]).reindex(full)
          .groupby(level="province")
          .transform(lambda s: s.interpolate(limit_direction="both"))
          .reset_index())
    if w[NORMAL_COLUMNS].isna().any().any():
        missing = sorted(w.loc[w["temp_avg_c"].isna(), "province"].unique())
        raise ValueError(f"no source weather at all for provinces: {missing}")
    return w


def add_anomaly(weather, normals):
    """anomaly_c = temp_avg_c minus the normal for that province and week of year."""
    keys = weather[["province"]].assign(woy=week_of_year(weather["week_start"]))
    normal = keys.join(normals, on=["province", "woy"])["temp_avg_c_normal"]
    return weather.assign(anomaly_c=(weather["temp_avg_c"] - normal).round(2))


def climate_normals(real):
    """Average weather per province x week of year, and each province's anomaly spread."""
    normals = (real.assign(woy=week_of_year(real["week_start"]))
                   .groupby(["province", "woy"])[NORMAL_COLUMNS].mean()
                   .add_suffix("_normal"))
    anomaly_sd = add_anomaly(real, normals).groupby("province")["anomaly_c"].std()
    return normals, anomaly_sd


def synthetic_weather(provinces, weeks, normals, anomaly_sd, seed):
    """Normal + random anomaly for each province x week, seeded per (province, week)."""
    rows = []
    for prov in provinces:
        for wk in weeks:
            rng = np.random.default_rng([seed, SEED_STREAM, province_key(prov), week_number(wk)])
            rows.append((prov, wk, rng.normal() * anomaly_sd[prov]))
    syn = pd.DataFrame(rows, columns=["province", "week_start", "anomaly_c"])
    syn["anomaly_c"] = syn["anomaly_c"].round(2)
    syn = syn.assign(woy=week_of_year(syn["week_start"])).join(normals, on=["province", "woy"])
    for t in ["max", "min", "avg"]:
        syn[f"temp_{t}_c"] = (syn[f"temp_{t}_c_normal"] + syn["anomaly_c"]).round(2)
    syn["precipitation"] = syn["precipitation_normal"]
    return syn[WEATHER_COLUMNS + ["anomaly_c"]]


def weekly_weather(source_path, provinces, start, end, seed):
    """Weather for every province and every Monday-Sunday week touching start..end.

    Real where the source has it, synthetic elsewhere. Columns: the contract weather
    columns + anomaly_c + is_synthetic.
    """
    real = load_source_weather(source_path, provinces)
    normals, anomaly_sd = climate_normals(real)

    first = start - pd.Timedelta(days=start.day_of_week)
    last = end - pd.Timedelta(days=end.day_of_week)
    weeks = pd.date_range(first, last, freq="7D")

    real = add_anomaly(real, normals)
    real = real[real["week_start"].isin(weeks)].assign(is_synthetic=False)

    have = set(real["week_start"])
    missing = [wk for wk in weeks if wk not in have]
    parts = [real]
    if missing:
        syn = synthetic_weather(provinces["province"], missing, normals, anomaly_sd, seed)
        parts.append(syn.assign(is_synthetic=True))
    return pd.concat(parts, ignore_index=True).sort_values(["province", "week_start"]).reset_index(drop=True)
