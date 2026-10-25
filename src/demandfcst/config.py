"""Project configuration (configs/data.toml)."""

import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]       # src/demandfcst/config.py -> project folder
CONFIG_PATH = PROJECT_ROOT / "configs" / "data.toml"


def load_config(path=CONFIG_PATH):
    with open(path, "rb") as f:                            # tomllib needs the file opened in binary mode
        return tomllib.load(f)

def locations(config=None, storage=None):
    """Absolute location of each area (local path or s3:// URL) for the chosen storage.

    `storage` overrides the config's "storage" value ("local" or "s3").
    """
    config = config or load_config()
    storage = storage or config["storage"]
    if storage not in ("local", "s3"):
        raise ValueError(f"storage must be 'local' or 's3', got {storage!r}")
    out = {}
    for area, loc in config["locations"][storage].items():
        loc = loc.format(bucket=config["s3"]["bucket"])
        out[area] = loc if "://" in loc else (PROJECT_ROOT / loc).as_posix()
    return out

def pipeline_paths(config=None):
    """Absolute local paths of the pipeline's working areas (raw, processed)."""
    config = config or load_config()
    return {area: (PROJECT_ROOT / rel).as_posix() for area, rel in config["pipeline"].items()}
