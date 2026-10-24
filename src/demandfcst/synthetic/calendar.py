"""Calendar rules for the synthetic sell-in generator.

Everything date-related lives here: Easter-based holidays, national and state
holidays, how events move sell-in (pre-load before, dip after), and how a week's
volume splits across its days. No randomness: same inputs, same outputs.
"""

import pandas as pd

# --- Day-of-week shipping pattern (Monday = 0 ... Sunday = 6) -------------------
DOW_WEIGHT = {0: 1.15, 1: 1.15, 2: 1.10, 3: 1.15, 4: 1.25, 5: 0.20, 6: 0.0}
HOLIDAY_DAY_WEIGHT = 0.1          # almost no deliveries on a holiday

# --- State holidays (MM-DD, province, name): placeholders until a real calendar arrives
STATE_HOLIDAYS = [
    ("07-09", "SP", "Revolução Constitucionalista"),
    ("04-23", "RJ", "São Jorge"),
    ("09-20", "RS", "Revolução Farroupilha"),
    ("12-19", "PR", "Emancipação do Paraná"),
    ("08-11", "SC", "Data Magna de Santa Catarina"),
    ("07-02", "BA", "Independência da Bahia"),
    ("03-06", "PE", "Revolução Pernambucana"),
    ("03-25", "CE", "Data Magna do Ceará"),
    ("06-24", "BA", "São João"), ("06-24", "PE", "São João"), ("06-24", "CE", "São João"),
]

# --- How events move sell-in: week offset from the event's week -> uplift --------
EVENT_PROFILES = {
    "Carnaval": {-2: 0.25, -1: 0.40, 0: 0.10, 1: -0.20},
    "Natal": {-2: 0.20, -1: 0.30, 0: 0.15, 1: 0.05, 2: -0.15},  # +1 = New Year, +2 = January dip
    "São João": {-1: 0.30, 0: 0.10, 1: -0.10},
    "Confraternização Universal": {},                           # covered by the Natal profile
}
DEFAULT_PROFILE = {-1: 0.04, 0: 0.06}                            # ordinary holiday: long weekend
CARNIVAL_STRENGTH = {"Sudeste": 1.0, "Sul": 0.6, "Nordeste": 1.3}
YEAR_STRENGTH = {("Carnaval", 2021): 0.2}                        # 2021 street Carnival cancelled
HOLIDAY_MULT_RANGE = (0.6, 1.8)
WEEK_EPOCH = pd.Timestamp("2000-01-03")      # a Monday; week numbers count from here


def week_start(dates):
    """Monday of the Monday-Sunday week each date falls in."""
    return dates - pd.to_timedelta(dates.dt.day_of_week, unit="D")

def week_number(week_starts):
    """Weeks since 2000-01-03: a stable integer per week, used in random seeds."""
    return (week_starts - WEEK_EPOCH) // pd.Timedelta(weeks=1)



def easter_sunday(year):
    """Gregorian Easter date (Meeus/Jones/Butcher algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return pd.Timestamp(year, month, day + 1)


def brazil_holidays(year):
    """National ("BR") and state holidays for one year: date, province, holiday_name."""
    e = easter_sunday(year)
    rows = [
        (pd.Timestamp(f"{year}-01-01"), "BR", "Confraternização Universal"),
        (e - pd.Timedelta(days=48), "BR", "Carnaval"),            # Monday
        (e - pd.Timedelta(days=47), "BR", "Carnaval"),            # Tuesday
        (e - pd.Timedelta(days=2), "BR", "Sexta-feira Santa"),
        (pd.Timestamp(f"{year}-04-21"), "BR", "Tiradentes"),
        (pd.Timestamp(f"{year}-05-01"), "BR", "Dia do Trabalho"),
        (e + pd.Timedelta(days=60), "BR", "Corpus Christi"),
        (pd.Timestamp(f"{year}-09-07"), "BR", "Independência"),
        (pd.Timestamp(f"{year}-10-12"), "BR", "Nossa Senhora Aparecida"),
        (pd.Timestamp(f"{year}-11-02"), "BR", "Finados"),
        (pd.Timestamp(f"{year}-11-15"), "BR", "Proclamação da República"),
        (pd.Timestamp(f"{year}-12-25"), "BR", "Natal"),
    ]
    if year >= 2024:                                              # national from 2024
        rows.append((pd.Timestamp(f"{year}-11-20"), "BR", "Consciência Negra"))
    rows += [(pd.Timestamp(f"{year}-{md}"), prov, name) for md, prov, name in STATE_HOLIDAYS]
    return pd.DataFrame(rows, columns=["date", "province", "holiday_name"])


def holiday_calendar(first_year, last_year):
    """All holidays from first_year to last_year (inclusive), in contract format."""
    years = range(first_year, last_year + 1)
    return pd.concat([brazil_holidays(y) for y in years], ignore_index=True)


def holidays_by_province(holidays, provinces):
    """Copy national ("BR") holidays to every province; keep state holidays for our provinces."""
    national = (holidays[holidays["province"] == "BR"].drop(columns="province")
                .merge(provinces[["province"]], how="cross"))
    state = holidays[holidays["province"].isin(provinces["province"])]
    return pd.concat([state, national], ignore_index=True)


def holiday_multipliers(holidays, provinces):
    """Sell-in multiplier per province x week from all events.

    `provinces` needs columns: province, region. Overlapping events add their uplifts.
    Returns: province, week_start, uplift, holiday_mult.
    """
    hol = holidays_by_province(holidays, provinces)
    hol["event_week"] = week_start(hol["date"])
    events = hol.drop_duplicates(["holiday_name", "province", "event_week"])  # Carnival Mon+Tue = 1
    region_of = provinces.set_index("province")["region"]

    rows = []
    for ev in events.itertuples(index=False):
        profile = EVENT_PROFILES.get(ev.holiday_name, DEFAULT_PROFILE)
        strength = YEAR_STRENGTH.get((ev.holiday_name, ev.event_week.year), 1.0)
        if ev.holiday_name == "Carnaval":
            strength *= CARNIVAL_STRENGTH[region_of[ev.province]]
        for offset, uplift in profile.items():
            rows.append((ev.province, ev.event_week + pd.Timedelta(weeks=offset), uplift * strength))

    uplifts = pd.DataFrame(rows, columns=["province", "week_start", "uplift"])
    out = uplifts.groupby(["province", "week_start"], as_index=False)["uplift"].sum()
    out["holiday_mult"] = (1 + out["uplift"]).clip(*HOLIDAY_MULT_RANGE)
    return out


def day_shares(holidays, provinces, start, end):
    """Share of each week's volume shipped on each day, per province, for start..end.

    Shares are computed over complete Monday-Sunday weeks, so a partial first or
    last week only gets the share of the days it actually contains.
    Returns: date, province, week_start, weight, is_holiday, day_share.
    """
    first_monday = start - pd.Timedelta(days=start.day_of_week)
    last_sunday = end + pd.Timedelta(days=6 - end.day_of_week)
    cal = (pd.DataFrame({"date": pd.date_range(first_monday, last_sunday, freq="D")})
           .merge(provinces[["province"]], how="cross"))
    cal["week_start"] = week_start(cal["date"])
    cal["weight"] = cal["date"].dt.day_of_week.map(DOW_WEIGHT)

    hol_days = holidays_by_province(holidays, provinces)[["province", "date"]].drop_duplicates()
    cal = cal.merge(hol_days.assign(is_holiday=True), on=["province", "date"], how="left")
    cal["is_holiday"] = cal["is_holiday"].notna()
    cal.loc[cal["is_holiday"], "weight"] *= HOLIDAY_DAY_WEIGHT

    cal["day_share"] = cal["weight"] / cal.groupby(["province", "week_start"])["weight"].transform("sum")
    return cal[(cal["date"] >= start) & (cal["date"] <= end)].reset_index(drop=True)
