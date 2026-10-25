"""Correction drops: sometimes the source re-sends earlier days with revised volumes.

Real extracts restate days after returns, invoice fixes or late postings. When a week is
released, with probability `prob` up to MAX_ROWS days from the previous LOOKBACK_WEEKS weeks
are re-sent with their volume x 0.85..1.15. Seeded per week, so every release is reproducible.
"""

import numpy as np
import pandas as pd

from demandfcst.synthetic.calendar import week_number
from demandfcst.synthetic.demand import generate_daily
from demandfcst.synthetic.weather import weekly_weather

LOOKBACK_WEEKS = 4
MAX_ROWS = 20
CHANGE_RANGE = (0.85, 1.15)
CORRECTION_STREAM = 4
COLUMNS = ["date", "province", "sku_id", "volume_hl", "volume_before"]


def corrections_for(monday, catalog, weather_source, seed, prob):
    """Rows re-sent with the release of the week starting `monday` (empty if none).

    Columns: the sellin_daily contract columns + volume_before (the value being corrected).
    """
    rng = np.random.default_rng([seed, CORRECTION_STREAM, week_number(monday)])
    if prob <= 0 or rng.random() >= prob:
        return pd.DataFrame(columns=COLUMNS)
    start, end = monday - pd.Timedelta(weeks=LOOKBACK_WEEKS), monday - pd.Timedelta(days=1)
    wx = weekly_weather(weather_source, catalog["provinces"], start, end, seed)
    earlier, _ = generate_daily(start, end, catalog, wx, seed)          # exactly what was delivered
    n = min(int(rng.integers(1, MAX_ROWS + 1)), len(earlier))
    picked = earlier.iloc[np.sort(rng.choice(len(earlier), size=n, replace=False))]
    factor = rng.uniform(*CHANGE_RANGE, n)
    return (picked.assign(volume_before=picked["volume_hl"],
                          volume_hl=(picked["volume_hl"] * factor).round(3).clip(lower=0.001))
            [COLUMNS].reset_index(drop=True))
    