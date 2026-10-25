"""Business-rule validation of the typed raw tables (contract section 5).

The reader already enforced the file-level contract (columns, types, encoding, empty
values). Here we check rules across rows, drops and datasets. Every finding is an Issue:
"error" stops processing, "warning" is kept in the report for a person to review.
"""

from dataclasses import dataclass

import pandas as pd

SALES_KEY = ["province", "sku_id", "date"]
WEATHER_KEY = ["province", "week_start"]
HOLIDAY_KEY = ["date", "province", "holiday_name"]
TEMPS = ["temp_min_c", "temp_avg_c", "temp_max_c"]
TEMP_RANGE_C = (-20, 50)
DROP_EVERY = pd.Timedelta(days=7)


@dataclass(frozen=True)
class Issue:
    level: str          # "error" | "warning"
    dataset: str
    check: str
    message: str


class ValidationError(ValueError):
    """Raised when the report contains errors. `report` holds every issue found."""

    def __init__(self, report):
        self.report = report
        errors = report[report["level"] == "error"]
        lines = [f"- [{r.dataset}] {r.check}: {r.message}" for r in errors.itertuples()]
        super().__init__(f"{len(errors)} validation error(s):\n" + "\n".join(lines))


def _found(level, dataset, check, rows, what, cols):
    """One Issue describing the offending rows (with up to 3 examples), or none if there are none."""
    if len(rows) == 0:
        return []
    examples = rows[cols].head(3).astype(str).to_dict("records")
    return [Issue(level, dataset, check, f"{len(rows)} {what}, e.g. {examples}")]


def validate_masters(provinces, skus, holidays):
    issues = []
    issues += _found("error", "province_master", "duplicate_province",
                     provinces[provinces.duplicated("province", keep=False)], "rows share a province code", ["province"])
    issues += _found("error", "sku_master", "duplicate_sku",
                     skus[skus.duplicated("sku_id", keep=False)], "rows share a sku_id", ["sku_id"])
    bad_pack = (skus["size_ml"] <= 0) | (skus["units_per_case"] <= 0)
    issues += _found("error", "sku_master", "bad_pack_size", skus[bad_pack],
                     "SKUs with size_ml or units_per_case <= 0", ["sku_id", "size_ml", "units_per_case"])
    backwards = (skus["launch_date"].notna() & skus["discontinue_date"].notna()
                 & (skus["launch_date"] > skus["discontinue_date"]))
    issues += _found("error", "sku_master", "lifecycle_dates", skus[backwards],
                     "SKUs launched after their discontinuation", ["sku_id", "launch_date", "discontinue_date"])
    issues += _found("error", "holidays", "duplicate_holiday",
                     holidays[holidays.duplicated(HOLIDAY_KEY, keep=False)], "rows share a date, province and name", HOLIDAY_KEY)
    known = holidays["province"].isin(provinces["province"]) | (holidays["province"] == "BR")
    issues += _found("warning", "holidays", "holiday_unknown_province", holidays[~known],
                     "holidays for provinces not in province_master", HOLIDAY_KEY)
    return issues


def validate_sales(sales, provinces, skus):
    d = "sellin_daily"
    issues = []
    in_drop = sales.duplicated([*SALES_KEY, "ingest_date"], keep=False)
    issues += _found("error", d, "duplicate_in_drop", sales[in_drop],
                     "rows share a key within one drop", [*SALES_KEY, "ingest_date"])
    restated = sales.duplicated(SALES_KEY, keep=False) & ~in_drop
    issues += _found("warning", d, "restated_rows", sales[restated],
                     "rows restate a day delivered in another drop (latest drop wins)", [*SALES_KEY, "ingest_date"])
    issues += _found("error", d, "volume_not_positive", sales[sales["volume_hl"] <= 0],
                     "rows with volume_hl <= 0", [*SALES_KEY, "volume_hl"])
    issues += _found("error", d, "unknown_province", sales[~sales["province"].isin(provinces["province"])],
                     "rows with a province not in province_master", SALES_KEY)
    issues += _found("error", d, "unknown_sku", sales[~sales["sku_id"].isin(skus["sku_id"])],
                     "rows with a sku_id not in sku_master", SALES_KEY)
    issues += _found("error", d, "date_after_ingest", sales[sales["date"] > sales["ingest_date"]],
                     "rows dated after their drop's ingest_date", [*SALES_KEY, "ingest_date"])

    drop_dates = pd.Series(sorted(sales["ingest_date"].unique()))
    late = drop_dates.diff() > DROP_EVERY
    gaps = pd.DataFrame({"previous": drop_dates.shift()[late], "ingest_date": drop_dates[late]})
    issues += _found("error", d, "missing_drop", gaps,
                     "drops arrive more than 7 days after the previous one", ["previous", "ingest_date"])

    own_week = sales["date"] > sales["ingest_date"] - DROP_EVERY
    rows_in_own_week = sales[own_week].groupby("ingest_date").size().reindex(drop_dates, fill_value=0)
    empty = rows_in_own_week[rows_in_own_week == 0].rename_axis("ingest_date").reset_index(name="rows")
    issues += _found("error", d, "drop_without_own_week", empty,
                     "drops with no sales in their own week", ["ingest_date"])

    life = skus.drop_duplicates("sku_id").set_index("sku_id")
    launch, disc = sales["sku_id"].map(life["launch_date"]), sales["sku_id"].map(life["discontinue_date"])
    outside = (launch.notna() & (sales["date"] < launch)) | (disc.notna() & (sales["date"] > disc))
    issues += _found("warning", d, "sales_outside_lifecycle", sales[outside],
                     "rows dated before launch or after discontinuation", SALES_KEY)
    return issues


def validate_weather(weather, provinces):
    d = "weather_weekly"
    issues = []
    issues += _found("error", d, "duplicate_weather", weather[weather.duplicated(WEATHER_KEY, keep=False)],
                     "rows share a province-week", [*WEATHER_KEY, "ingest_date"])
    issues += _found("error", d, "week_not_monday", weather[weather["week_start"].dt.day_of_week != 0],
                     "week_start values that are not Mondays", WEATHER_KEY)
    issues += _found("error", d, "unknown_province", weather[~weather["province"].isin(provinces["province"])],
                     "rows with a province not in province_master", WEATHER_KEY)

    weeks = pd.date_range(weather["week_start"].min(), weather["week_start"].max(), freq="7D")
    grid = pd.MultiIndex.from_product([provinces["province"], weeks], names=WEATHER_KEY).to_frame(index=False)
    missing = (grid.merge(weather[WEATHER_KEY].drop_duplicates(), how="left", indicator=True)
                   .query("_merge == 'left_only'"))
    issues += _found("error", d, "missing_weather_week", missing, "province-weeks with no weather", WEATHER_KEY)

    in_order = (weather["temp_min_c"] <= weather["temp_avg_c"]) & (weather["temp_avg_c"] <= weather["temp_max_c"])
    issues += _found("error", d, "temperature_order", weather[~in_order],
                     "rows where min <= avg <= max does not hold", [*WEATHER_KEY, *TEMPS])
    lo, hi = TEMP_RANGE_C
    outside = ((weather[TEMPS] < lo) | (weather[TEMPS] > hi)).any(axis=1)
    issues += _found("error", d, "temperature_range", weather[outside],
                     f"rows with a temperature outside {lo}..{hi} °C", [*WEATHER_KEY, *TEMPS])
    issues += _found("error", d, "negative_precipitation", weather[weather["precipitation"] < 0],
                     "rows with negative precipitation", [*WEATHER_KEY, "precipitation"])
    return issues


def validate_cross(sales, weather):
    """Rules that need two datasets together."""
    week_start = sales["date"] - pd.to_timedelta(sales["date"].dt.day_of_week, unit="D")
    sales_weeks = sales[["province"]].assign(week_start=week_start).drop_duplicates()
    missing = (sales_weeks.merge(weather[WEATHER_KEY].drop_duplicates(), how="left", indicator=True)
                          .query("_merge == 'left_only'"))
    return _found("error", "sellin_daily", "sales_without_weather", missing,
                  "province-weeks with sales but no weather", WEATHER_KEY)


def validate(tables):
    """Run every check on the tables from reader.read_all(). Returns the report; raises nothing."""
    t = tables
    issues = (validate_masters(t["province_master"], t["sku_master"], t["holidays"])
              + validate_sales(t["sellin_daily"], t["province_master"], t["sku_master"])
              + validate_weather(t["weather_weekly"], t["province_master"])
              + validate_cross(t["sellin_daily"], t["weather_weekly"]))
    return pd.DataFrame(issues, columns=["level", "dataset", "check", "message"])


def raise_if_errors(report):
    """Stop the pipeline if the report has any error (warnings are allowed through)."""
    if (report["level"] == "error").any():
        raise ValidationError(report)
