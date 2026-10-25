import pandas as pd
import pytest

from demandfcst.synthetic import landing
from demandfcst.synthetic.catalog import build_catalog

INGEST = pd.Timestamp("2024-12-29")


def test_write_drop_uses_contract_layout_and_iso_dates(tmp_path):
    df = pd.DataFrame({"date": pd.to_datetime(["2024-12-23"]), "province": ["SP"],
                       "sku_id": ["00123"], "volume_hl": [1.5]})
    location = landing.write_drop(df, tmp_path, "sellin_daily", INGEST)
    assert location.endswith("sellin_daily/ingest_date=2024-12-29/part.csv")
    with open(location, "rb") as f:
        raw = f.read()
    assert raw.startswith(b"date,province,sku_id,volume_hl")         # header first: no BOM
    assert b"2024-12-23,SP,00123,1.5" in raw                          # ISO date, code kept as text


def test_complete_drop_is_refused(tmp_path):
    df = pd.DataFrame({"a": [1]})
    landing.write_drop(df, tmp_path, "sellin_daily", INGEST)
    with pytest.raises(FileExistsError):                              # same file twice
        landing.write_drop(df, tmp_path, "sellin_daily", INGEST)
    landing.mark_complete(tmp_path, "sellin_daily", INGEST)
    with pytest.raises(FileExistsError):                              # delivered drop
        landing.ensure_new_drop(tmp_path, ["sellin_daily"], INGEST)


def test_incomplete_drop_is_cleared_for_a_rewrite(tmp_path):
    landing.write_drop(pd.DataFrame({"a": [1]}), tmp_path, "sellin_daily", INGEST)   # crashed: no marker
    assert not landing.is_complete(tmp_path, "sellin_daily", INGEST)
    landing.ensure_new_drop(tmp_path, ["sellin_daily"], INGEST)                      # clears it
    assert not landing.is_complete(tmp_path, "sellin_daily", INGEST)
    landing.write_drop(pd.DataFrame({"a": [2]}), tmp_path, "sellin_daily", INGEST)   # rewrite works
    landing.mark_complete(tmp_path, "sellin_daily", INGEST)
    assert landing.is_complete(tmp_path, "sellin_daily", INGEST)


def test_masters_have_exactly_the_contract_columns():
    cat = build_catalog(42)
    assert list(landing.province_master(cat).columns) == ["province", "province_name", "region"]
    assert list(landing.sku_master(cat).columns) == landing.SKU_MASTER_COLUMNS
    assert "popularity" not in landing.sku_master(cat).columns
