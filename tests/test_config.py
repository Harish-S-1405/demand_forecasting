import pytest

from demandfcst import config

CFG = {"storage": "local",
       "s3": {"bucket": "my-bucket", "region": "x"},
       "locations": {"local": {"landing": "landing"}, "s3": {"landing": "s3://{bucket}/landing"}}}


def test_locations_for_each_storage():
    assert config.locations(CFG)["landing"].endswith("/landing")
    assert config.locations(CFG, storage="s3")["landing"] == "s3://my-bucket/landing"
    with pytest.raises(ValueError):
        config.locations(CFG, storage="gcs")
