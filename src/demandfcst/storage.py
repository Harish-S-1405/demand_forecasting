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

def touch(location):
    """Create an empty file, e.g. a _SUCCESS marker."""
    write_text(location, "")


def remove(location):
    """Delete a file, or a folder with everything in it. No error if it doesn't exist."""
    fs, path = fs_for(location)
    if fs.exists(path):
        fs.rm(path, recursive=True)

def read_head(location, n):
    """The first n bytes of a file (cheap, even on S3: only a small block is fetched)."""
    fs, path = fs_for(location)
    with fs.open(path, "rb", block_size=1024) as f:
        return f.read(n)

def list_files(location):
    """Names of the files directly inside a folder, sorted."""
    fs, path = fs_for(location)
    return sorted(p.rstrip("/").split("/")[-1] for p in fs.ls(path, detail=False) if fs.isfile(p))


def copy_file(src, dst):
    """Copy a file byte for byte between any two locations (e.g. S3 -> local). Returns bytes copied."""
    src_fs, src_path = fs_for(src)
    dst_fs, dst_path = fs_for(dst)
    dst_fs.makedirs(dst_path.rsplit("/", 1)[0], exist_ok=True)
    with src_fs.open(src_path, "rb") as fin:
        data = fin.read()
    with dst_fs.open(dst_path, "wb") as fout:
        fout.write(data)
    return len(data)

def write_parquet(df, location):
    """Write a DataFrame as Parquet (types kept exactly), creating parent folders."""
    fs, path = fs_for(location)
    fs.makedirs(path.rsplit("/", 1)[0], exist_ok=True)
    with fs.open(path, "wb") as f:
        df.to_parquet(f, index=False)


def move(src, dst):
    """Move a file or folder (dst must not exist yet)."""
    fs, src_path = fs_for(src)
    _, dst_path = fs_for(dst)
    fs.mv(src_path, dst_path, recursive=True)
