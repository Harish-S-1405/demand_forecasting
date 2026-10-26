"""One chart style for all EDA notebooks, so figures look consistent in reports and the dashboard."""

from pathlib import Path

import matplotlib.pyplot as plt

from demandfcst import config

REGION_COLORS = {"Sudeste": "#2f5fa8", "Sul": "#2f7d5b", "Nordeste": "#c0700a"}
FIG_DIR = Path(config.PROJECT_ROOT) / "outputs" / "eda" / "figures"


def apply():
    """Set the house style for every chart drawn after this call."""
    plt.rcParams.update({
        "figure.figsize": (11, 4), "figure.dpi": 110,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.alpha": 0.3,
        "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "legend.frameon": False,
    })


def save(fig, name):
    """Save a figure as outputs/eda/figures/<name>.png: evidence for the insight log."""
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = FIG_DIR / f"{name}.png"
    fig.savefig(path, bbox_inches="tight")
    return path
