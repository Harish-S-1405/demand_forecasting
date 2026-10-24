import numpy as np
import pandas as pd
import pytest

from demandfcst.synthetic.catalog import build_provinces


@pytest.fixture
def fake_weather_source(tmp_path):
    """Source-format weekly weather (2021-2023) for every catalog province; returns its path."""
    weeks = pd.date_range("2021-01-04", "2023-12-25", freq="7D")
    rows = []
    for j, prov in enumerate(build_provinces()["province"]):
        for i, wk in enumerate(weeks):
            temp = 65 + j + 10 * np.cos(2 * np.pi * i / 52) + (i % 5 - 2)
            rows.append({"Version.[Version Name]": "CurrentWorkingView",
                         "Time.[FiscalWeek]": wk.strftime("%m/%d/%Y"),
                         "Sales Domain.[Province]": prov,
                         "Max Weighted Temp": temp + 8, "Min Weighted Temp": temp - 8,
                         "Weighted Precipitation": 0.3, "Weighted Temperature": temp})
    path = tmp_path / "weather_source.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path
