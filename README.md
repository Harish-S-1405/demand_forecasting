# Demand Forecasting (demandfcst)

Weekly demand forecasting for a beverage company at **province x SKU** level,
12 weeks ahead.

The goal is to beat a statistical benchmark (the kind of models a planning
platform such as o9 ships) on the forecasts that drive real decisions:
**lag 2** (production locks) and **lag 4** (materials and brewing lock).

- **Accuracy** = 1 - sum(|forecast - actual|) / sum(actual)
- **Bias** = (sum(forecast) - sum(actual)) / sum(actual)

## Setup

    py -3.11 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt

## Project layout

    data/raw/         original input files (never edited by hand)
    data/processed/   cleaned tables produced by code
    notebooks/        exploration and analysis
    src/              reusable Python functions
    outputs/          plots, forecasts and metrics
