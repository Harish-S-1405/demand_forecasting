"""The data contract (docs/phase2_data_source/01_data_contract.md) as code.

Every pipeline step reads column names, types and keys from SCHEMAS instead of typing
them again. Files are read as text first and converted on purpose, so codes keep their
leading zeros and every value that breaks the contract is reported, all at once.
"""

from dataclasses import dataclass

import pandas as pd
from demandfcst import storage


BOM = "\ufeff"
BOM_BYTES = BOM.encode("utf-8")              # b"\xef\xbb\xbf"
BOM_PROBLEM = "file starts with a BOM (byte order mark): save it as UTF-8 without BOM"

BOOLS = {"True": True, "False": False, "true": True, "false": False}


@dataclass(frozen=True)
class Column:
    name: str
    kind: str                 # "text" | "date" | "float" | "int" | "bool"
    nullable: bool = False


@dataclass(frozen=True)
class Dataset:
    name: str
    columns: tuple
    key: tuple                # columns that identify one row
    grain: str                # "daily" | "weekly" | "snapshot"

    @property
    def column_names(self):
        return [c.name for c in self.columns]


def _text(*names):
    return tuple(Column(n, "text") for n in names)


SCHEMAS = {d.name: d for d in [
    Dataset("sellin_daily",
            (Column("date", "date"), *_text("province", "sku_id"), Column("volume_hl", "float")),
            key=("province", "sku_id", "date"), grain="daily"),
    Dataset("weather_weekly",
            (Column("province", "text"), Column("week_start", "date"),
             Column("temp_max_c", "float"), Column("temp_min_c", "float"),
             Column("temp_avg_c", "float"), Column("precipitation", "float")),
            key=("province", "week_start"), grain="weekly"),
    Dataset("province_master",
            _text("province", "province_name", "region"),
            key=("province",), grain="snapshot"),
    Dataset("sku_master",
            (*_text("sku_id", "sku_name", "brand", "pack", "container"),
             Column("size_ml", "int"), Column("units_per_case", "int"), Column("returnable", "bool"),
             Column("launch_date", "date", nullable=True), Column("discontinue_date", "date", nullable=True)),
            key=("sku_id",), grain="snapshot"),
    Dataset("holidays",
            (Column("date", "date"), *_text("province", "holiday_name")),
            key=("date", "province", "holiday_name"), grain="snapshot"),
    Dataset("sales_weekly",                                   # processed: produced by the pipeline
            (*_text("province", "sku_id"), Column("week_start", "date"), Column("volume_hl", "float")),
            key=("province", "sku_id", "week_start"), grain="weekly"),
]}


class SchemaError(ValueError):
    """A file that breaks the contract. `problems` lists every issue found."""

    def __init__(self, dataset, problems):
        self.dataset = dataset
        self.problems = problems
        super().__init__(f"{dataset}: " + "; ".join(problems))


def _convert(raw, kind):
    """Convert one text column. Returns (values, bad): bad marks values that don't fit `kind`."""
    present = raw.notna()
    if kind == "text":
        values = raw.astype("str")
    elif kind == "date":
        values = pd.to_datetime(raw, format="%Y-%m-%d", errors="coerce")
    elif kind == "float":
        values = pd.to_numeric(raw, errors="coerce").astype("float64")
    elif kind == "int":
        num = pd.to_numeric(raw, errors="coerce")
        whole = num.notna() & (num % 1 == 0)
        return num.where(whole).astype("Int64"), present & ~whole
    elif kind == "bool":
        values = raw.map(BOOLS).astype("boolean")
    else:
        raise ValueError(f"unknown column kind {kind!r}")
    return values, present & values.isna()


def coerce(raw, schema):
    """Convert a text DataFrame to the schema's types; raise SchemaError listing every problem."""
    problems = []
    if any(str(c).startswith(BOM) for c in raw.columns):
        problems.append(BOM_PROBLEM)    
    missing = [c for c in schema.column_names if c not in raw.columns]
    unexpected = [c for c in raw.columns if c not in schema.column_names]
    if missing:
        problems.append(f"missing columns: {missing}")
    if unexpected:
        problems.append(f"unexpected columns: {unexpected}")
    if problems:
        raise SchemaError(schema.name, problems)

    typed = {}
    for col in schema.columns:
        values, bad = _convert(raw[col.name], col.kind)
        if bad.any():
            examples = raw.loc[bad, col.name].unique()[:3].tolist()
            problems.append(f"{col.name}: {bad.sum()} value(s) are not {col.kind}, e.g. {examples}")
        empty = values.isna() & ~bad
        if not col.nullable and empty.any():
            problems.append(f"{col.name}: {empty.sum()} empty value(s)")
        typed[col.name] = values
    if problems:
        raise SchemaError(schema.name, problems)
    return pd.DataFrame(typed)


def read_csv(location, schema):
    """Read one contract CSV (local path or URL) as text, then convert it with coerce()."""
    if storage.read_head(location, len(BOM_BYTES)) == BOM_BYTES:   # pandas would silently drop it
        raise SchemaError(schema.name, [BOM_PROBLEM])
    raw = pd.read_csv(location, dtype=str, encoding="utf-8", keep_default_na=False, na_values=[""])
    return coerce(raw, schema)

