import pandas as pd
import pytest

from demandfcst.pipeline import schema
from demandfcst.synthetic import landing
from demandfcst.synthetic.calendar import holiday_calendar
from demandfcst.synthetic.catalog import build_catalog
from demandfcst.synthetic.demand import generate_daily
from demandfcst.synthetic.weather import WEATHER_COLUMNS, weekly_weather

SELLIN = schema.SCHEMAS["sellin_daily"]


def test_every_contract_dataset_is_defined():
    assert set(schema.SCHEMAS) == {"sellin_daily", "weather_weekly", "province_master",
                                   "sku_master", "holidays", "sales_weekly"}


def test_valid_rows_get_contract_types():
    raw = pd.DataFrame({"date": ["2024-01-01"], "province": ["SP"], "sku_id": ["00123"], "volume_hl": ["1.5"]})
    typed = schema.coerce(raw, SELLIN)
    assert typed.loc[0, "sku_id"] == "00123"                        # leading zeros kept
    assert typed["date"].dtype.kind == "M"                          # M = datetime
    assert typed.loc[0, "volume_hl"] == 1.5


def test_all_problems_reported_at_once():
    raw = pd.DataFrame({"date": ["2024-01-01", "01/02/2024"], "province": ["SP", None],
                        "sku_id": ["00123", "38958"], "volume_hl": ["1.5", "abc"]})
    with pytest.raises(schema.SchemaError) as err:
        schema.coerce(raw, SELLIN)
    assert len(err.value.problems) == 3


def test_missing_and_unexpected_columns():
    raw = pd.DataFrame({"date": ["2024-01-01"], "province": ["SP"], "sku": ["1"], "volume_hl": ["1"]})
    with pytest.raises(schema.SchemaError) as err:
        schema.coerce(raw, SELLIN)
    assert any("missing" in p and "sku_id" in p for p in err.value.problems)
    assert any("unexpected" in p and "sku" in p for p in err.value.problems)


def test_bom_is_reported(tmp_path):
    path = tmp_path / "part.csv"
    path.write_text("date,province,sku_id,volume_hl\n2024-01-01,SP,00123,1.5\n", encoding="utf-8-sig")
    with pytest.raises(schema.SchemaError, match="BOM"):
        schema.read_csv(path, SELLIN)


def test_generator_output_passes_the_schema(tmp_path, fake_weather_source):
    """Contract test: what the producer writes, the consumer can read."""
    root = f"memory://{tmp_path.name}"
    cat = build_catalog(42)
    start, end = pd.Timestamp("2024-12-30"), pd.Timestamp("2025-01-05")
    wx = weekly_weather(fake_weather_source, cat["provinces"], start, end, 42)
    sales, _ = generate_daily(start, end, cat, wx, 42)
    outputs = {"sellin_daily": sales, "weather_weekly": wx[WEATHER_COLUMNS],
               "province_master": landing.province_master(cat), "sku_master": landing.sku_master(cat),
               "holidays": holiday_calendar(2024, 2025)}
    for name, df in outputs.items():
        location = landing.write_drop(df, root, name, end)
        typed = schema.read_csv(location, schema.SCHEMAS[name])
        assert len(typed) == len(df), name
