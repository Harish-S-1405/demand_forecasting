"""Read and write files the same way whether they live on the local disk or in S3.

Every location is a plain string: a local path ("C:/.../landing") or a URL
("s3://bucket/landing", "memory://test"). fsspec picks the right filesystem from it,
so no other module needs to know where the data is. This is the only module that
touches files directly.
"""

import fsspec


def fs_for(location):
    """(filesystem, path-without-protocol) for a local path or URL."""
    return fsspec.core.url_to_fs(str(location))


def join(*parts):
    """Join location parts with "/" (works for local paths and URLs)."""
    return "/".join(str(p).rstrip("/\\") for p in parts)


def exists(location):
    fs, path = fs_for(location)
    return fs.exists(path)


def list_dirs(location, pattern):
    """Names of the sub-folders of `location` matching a glob pattern, sorted."""
    fs, path = fs_for(location)
    return sorted(p.rstrip("/").split("/")[-1] for p in fs.glob(f"{path}/{pattern}") if fs.isdir(p))


def write_csv(df, location, **to_csv_kwargs):
    """Write a DataFrame as UTF-8 CSV (no BOM, no index), creating parent folders."""
    fs, path = fs_for(location)
    fs.makedirs(path.rsplit("/", 1)[0], exist_ok=True)
    with fs.open(path, "w", encoding="utf-8", newline="") as f:
        df.to_csv(f, index=False, **to_csv_kwargs)


def write_text(location, text):
    fs, path = fs_for(location)
    fs.makedirs(path.rsplit("/", 1)[0], exist_ok=True)
    with fs.open(path, "w", encoding="utf-8") as f:
        f.write(text)


def read_text(location):
    fs, path = fs_for(location)
    with fs.open(path, "r", encoding="utf-8") as f:
        return f.read()
