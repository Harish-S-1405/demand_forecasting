"""Create and secure the project's S3 bucket. Safe to run again.

Run from the project root:
    python scripts/setup_s3.py
"""

import logging
import re

import boto3
from botocore.exceptions import ClientError

from demandfcst.config import load_config

log = logging.getLogger("setup_s3")

BUCKET_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$")
OLD_VERSION_DAYS = 30


def create_bucket(s3, bucket, region):
    """Create the bucket unless it already exists in this account."""
    try:
        s3.head_bucket(Bucket=bucket)
        log.info("bucket %s already exists and is yours", bucket)
        return
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("403", "Forbidden"):
            raise SystemExit(f"bucket name '{bucket}' belongs to another AWS account; choose another name")
        if code not in ("404", "NoSuchBucket", "NotFound"):
            raise

    kwargs = {"Bucket": bucket}
    if region != "us-east-1":                               # us-east-1 must NOT get a LocationConstraint
        kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region}
    s3.create_bucket(**kwargs)
    log.info("created bucket %s in %s", bucket, region)


def secure_bucket(s3, bucket):
    s3.put_public_access_block(Bucket=bucket, PublicAccessBlockConfiguration={
        "BlockPublicAcls": True, "IgnorePublicAcls": True,
        "BlockPublicPolicy": True, "RestrictPublicBuckets": True})
    log.info("public access blocked")

    s3.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
    log.info("versioning enabled")

    s3.put_bucket_encryption(Bucket=bucket, ServerSideEncryptionConfiguration={
        "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]})
    log.info("default encryption: AES256")

    s3.put_bucket_lifecycle_configuration(Bucket=bucket, LifecycleConfiguration={"Rules": [{
        "ID": "expire-old-versions", "Status": "Enabled", "Filter": {"Prefix": ""},
        "NoncurrentVersionExpiration": {"NoncurrentDays": OLD_VERSION_DAYS}}]})
    log.info("lifecycle: old versions deleted after %d days", OLD_VERSION_DAYS)

    s3.put_bucket_tagging(Bucket=bucket, Tagging={"TagSet": [{"Key": "project", "Value": "demandfcst"}]})
    log.info("tag: project=demandfcst")


def check_bucket(s3, bucket):
    """Read the settings back from AWS, so we see what is really configured."""
    region = s3.get_bucket_location(Bucket=bucket)["LocationConstraint"] or "us-east-1"
    versioning = s3.get_bucket_versioning(Bucket=bucket).get("Status")
    blocked = all(s3.get_public_access_block(Bucket=bucket)["PublicAccessBlockConfiguration"].values())
    encryption = (s3.get_bucket_encryption(Bucket=bucket)["ServerSideEncryptionConfiguration"]
                  ["Rules"][0]["ApplyServerSideEncryptionByDefault"]["SSEAlgorithm"])
    log.info("check: region=%s versioning=%s public_access_blocked=%s encryption=%s",
             region, versioning, blocked, encryption)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_config()["s3"]
    bucket, region = cfg["bucket"], cfg["region"]
    if not BUCKET_NAME.match(bucket):
        raise SystemExit(f"invalid bucket name '{bucket}': use 3-63 lowercase letters, digits or hyphens")

    s3 = boto3.client("s3", region_name=region)
    create_bucket(s3, bucket, region)
    secure_bucket(s3, bucket)
    check_bucket(s3, bucket)


if __name__ == "__main__":
    main()
