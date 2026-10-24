"""Turn the catalog, calendar and weather into daily sell-in rows.

generate_daily(start, end, ...) works on whole Monday-Sunday weeks and seeds every
random draw per (series, week), so a week comes out identical whether it is generated
alone (weekly release) or inside the full history.
"""

import numpy as np
import pandas as pd

from demandfcst.synthetic import calendar
from demandfcst.synthetic.calendar import week_number, week_start

TREND_ORIGIN = pd.Timestamp("2021-01-01")       # trend multiplier = 1.0 on this date
SEASON_PEAK_DOY = 15                            # mid-January
WEATHER_MULT_RANGE = (0.7, 1.3)
LAUNCH_START_SHARE = 0.2                        # new SKUs start at 20% ...
LAUNCH_RAMP_WEEKS = 8                           # ... and reach 100% after 8 weeks
PROMO_DEPTH_RANGE = (0.4, 1.0)                  # promo week: +40% ... +100%
PROMO_PROFILE = {0: 1.0, 1: -0.4, 2: -0.15}     # spike, then sell-through dip
PROMO_MULT_RANGE = (0.5, 2.2)
PROMO_LOOKBACK_WEEKS = 4                        # earlier weeks needed for dips and spacing
PROMO_STREAM = 2
NOISE_STREAM = 3
MIN_VOLUME_HL = 0.0005                          # below this a day counts as no sale


def whole_weeks(start, end):
    """Mondays of every Monday-Sunday week touching start..end."""
    first = start - pd.Timedelta(days=start.day_of_week)
    last = end - pd.Timedelta(days=end.day_of_week)
    return pd.date_range(first, last, freq="7D")


def promotions(series, weeks, seed):
    """Promotion weeks and depths, seeded per (series, week).

    A week is a promotion if its draw hits promo_rate and neither of the two previous
    weeks' draws did (promotions at least 3 weeks apart). Includes the two weeks before
    `weeks` so their sell-through dips reach into the range.
    Returns: province, sku_id, week_start, uplift.
    """
    lookback = pd.date_range(weeks[0] - pd.Timedelta(weeks=PROMO_LOOKBACK_WEEKS), weeks[-1], freq="7D")
    rows = []
    for s in series[series["promo_rate"] > 0].itertuples(index=False):
        raw, depth = [], []
        for wk in lookback:
            rng = np.random.default_rng([seed, PROMO_STREAM, int(s.series_num), week_number(wk)])
            raw.append(rng.random() < s.promo_rate)
            depth.append(rng.uniform(*PROMO_DEPTH_RANGE))
        for i in range(2, len(lookback)):
            if raw[i] and not raw[i - 1] and not raw[i - 2]:
                rows.append((s.province, s.sku_id, lookback[i], round(depth[i], 2)))
    return pd.DataFrame(rows, columns=["province", "sku_id", "week_start", "uplift"])


def promo_multipliers(promos):
    """Spread each promotion over its week and the two sell-through weeks after it."""
    parts = [promos.assign(week_start=promos["week_start"] + pd.Timedelta(weeks=offset),
                           promo_uplift=promos["uplift"] * share)
             for offset, share in PROMO_PROFILE.items()]
    eff = (pd.concat(parts)
           .groupby(["province", "sku_id", "week_start"], as_index=False)["promo_uplift"].sum())
    eff["promo_mult"] = (1 + eff["promo_uplift"]).clip(*PROMO_MULT_RANGE)
    return eff[["province", "sku_id", "week_start", "promo_mult"]]


def life_multiplier(grid, skus):
    """0 before launch and after discontinuation; 20% -> 100% ramp over a launch's first weeks."""
    life = skus.set_index("sku_id")
    launch = grid["sku_id"].map(life["launch_date"])
    disc = grid["sku_id"].map(life["discontinue_date"])
    weeks_live = (grid["date"] - launch).dt.days / 7
    ramp = (LAUNCH_START_SHARE + (1 - LAUNCH_START_SHARE) * weeks_live / LAUNCH_RAMP_WEEKS).clip(upper=1.0)
    mult = pd.Series(np.where(launch.notna(), ramp, 1.0), index=grid.index)
    mult[launch.notna() & (grid["date"] < launch)] = 0.0
    mult[disc.notna() & (grid["date"] > disc)] = 0.0
    return mult


def expected_grid(catalog, weather, weeks, promos):
    """Expected daily volume (no noise) for every series and every day of `weeks`."""
    series, skus, provinces = catalog["series"], catalog["skus"], catalog["provinces"]
    days = pd.date_range(weeks[0], weeks[-1] + pd.Timedelta(days=6), freq="D")
    grid = (series[["series_num", "province", "sku_id", "base_hl_week", "trend_per_year",
                    "season_amp", "weather_beta"]]
            .merge(pd.DataFrame({"date": days}), how="cross"))
    grid["week_start"] = week_start(grid["date"])

    t_years = (grid["date"] - TREND_ORIGIN).dt.days / 365.25
    grid["trend_mult"] = (1 + grid["trend_per_year"]) ** t_years
    doy = grid["date"].dt.day_of_year
    grid["season_mult"] = 1 + grid["season_amp"] * np.cos(2 * np.pi * (doy - SEASON_PEAK_DOY) / 365.25)

    grid = grid.merge(weather[["province", "week_start", "anomaly_c"]],
                      on=["province", "week_start"], how="left")
    if grid["anomaly_c"].isna().any():
        raise ValueError("weather is missing for some province-weeks in the range")
    grid["weather_mult"] = (1 + grid["weather_beta"] * grid["anomaly_c"]).clip(*WEATHER_MULT_RANGE)

    holidays = calendar.holiday_calendar(days[0].year - 1, days[-1].year + 1)   # events spill across years
    hol = calendar.holiday_multipliers(holidays, provinces)
    grid = grid.merge(hol[["province", "week_start", "holiday_mult"]],
                      on=["province", "week_start"], how="left")
    grid["holiday_mult"] = grid["holiday_mult"].fillna(1.0)

    if len(promos):
        grid = grid.merge(promo_multipliers(promos), on=["province", "sku_id", "week_start"], how="left")
        grid["promo_mult"] = grid["promo_mult"].fillna(1.0)
    else:
        grid["promo_mult"] = 1.0

    shares = calendar.day_shares(holidays, provinces, days[0], days[-1])
    grid = grid.merge(shares[["province", "date", "day_share"]], on=["province", "date"], how="left")
    grid["life_mult"] = life_multiplier(grid, skus)

    grid["expected_hl"] = (grid["base_hl_week"] * grid["trend_mult"] * grid["season_mult"]
                           * grid["weather_mult"] * grid["holiday_mult"] * grid["promo_mult"]
                           * grid["life_mult"] * grid["day_share"])
    return grid.sort_values(["series_num", "date"]).reset_index(drop=True)


def draw_sales(grid, series, n_weeks, seed):
    """Actual daily volumes, with one random generator per (series, week)."""
    n_series = len(series)
    expected = grid["expected_hl"].to_numpy().reshape(n_series, n_weeks, 7)
    shares = grid["day_share"].to_numpy().reshape(n_series, n_weeks, 7)
    week_nums = week_number(grid["week_start"]).to_numpy().reshape(n_series, n_weeks, 7)[0, :, 0]
    volume = np.zeros_like(expected)

    for i, s in enumerate(series.sort_values("series_num").itertuples(index=False)):
        cv2 = s.noise_cv ** 2
        for w in range(n_weeks):
            rng = np.random.default_rng([seed, NOISE_STREAM, int(s.series_num), int(week_nums[w])])
            exp = expected[i, w]
            if s.week_cv > 0:                                    # erratic: the whole week scaled
                wcv2 = s.week_cv ** 2
                exp = exp * rng.gamma(1 / wcv2, wcv2)
            if s.order_prob >= 1:                                # dense: every delivery day
                volume[i, w] = rng.gamma(1 / cv2, exp * cv2)
            else:                                                # sparse: some weeks, one day
                week_total = exp.sum()
                if week_total > 0 and rng.random() < s.order_prob:
                    size = rng.gamma(1 / cv2, week_total / s.order_prob * cv2)
                    day = np.argmax(shares[i, w] * rng.random(7))
                    volume[i, w, day] = size
    return volume.reshape(-1)


def generate_daily(start, end, catalog, weather, seed):
    """Daily sell-in rows for start..end in contract format, plus the promotions answer key.

    `weather` must cover every week touching start..end (see weather.weekly_weather).
    Returns (sales, promos): sales = date, province, sku_id, volume_hl (only days with sales);
    promos = province, sku_id, week_start, uplift for the weeks in the range.
    """
    weeks = whole_weeks(start, end)
    promos = promotions(catalog["series"], weeks, seed)
    grid = expected_grid(catalog, weather, weeks, promos)
    grid["volume_hl"] = draw_sales(grid, catalog["series"], len(weeks), seed)

    keep = (grid["date"] >= start) & (grid["date"] <= end) & (grid["volume_hl"] > MIN_VOLUME_HL)
    sales = (grid.loc[keep, ["date", "province", "sku_id", "volume_hl"]]
             .assign(volume_hl=lambda d: d["volume_hl"].round(3))
             .sort_values(["date", "province", "sku_id"])
             .reset_index(drop=True))
    return sales, promos[promos["week_start"].isin(weeks)].reset_index(drop=True)
