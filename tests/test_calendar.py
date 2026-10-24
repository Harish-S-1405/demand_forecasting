import pandas as pd
import pytest

from demandfcst.synthetic.calendar import (
    brazil_holidays,
    day_shares,
    easter_sunday,
    holiday_calendar,
    holiday_multipliers,
)

PROVINCES = pd.DataFrame({"province": ["SP", "RS", "BA"], "region": ["Sudeste", "Sul", "Nordeste"]})


@pytest.mark.parametrize("year, expected", [
    (2021, "2021-04-04"),
    (2023, "2023-04-09"),
    (2024, "2024-03-31"),
    (2025, "2025-04-20"),
])
def test_easter_known_dates(year, expected):
    assert easter_sunday(year) == pd.Timestamp(expected)


def test_carnival_2024_is_12_and_13_february():
    hol = brazil_holidays(2024)
    carnival = hol.loc[hol["holiday_name"] == "Carnaval", "date"].tolist()
    assert carnival == [pd.Timestamp("2024-02-12"), pd.Timestamp("2024-02-13")]


def test_day_shares_sum_to_one_every_week():
    hol = holiday_calendar(2023, 2024)
    shares = day_shares(hol, PROVINCES, pd.Timestamp("2023-01-02"), pd.Timestamp("2024-12-29"))
    weekly = shares.groupby(["province", "week_start"])["day_share"].sum()
    assert (weekly.round(9) == 1).all()


def test_no_shipments_on_sunday():
    hol = holiday_calendar(2024, 2024)
    shares = day_shares(hol, PROVINCES, pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-29"))
    assert (shares.loc[shares["date"].dt.day_of_week == 6, "day_share"] == 0).all()


def test_carnival_preload_strongest_in_nordeste():
    hol = holiday_calendar(2023, 2023)
    mult = holiday_multipliers(hol, PROVINCES).set_index(["province", "week_start"])["holiday_mult"]
    week_before = pd.Timestamp("2023-02-13")              # Carnival 2023 = week of 20 Feb
    assert mult[("BA", week_before)] > mult[("SP", week_before)] > mult[("RS", week_before)]
