"""Copy every bucket of the old dev MinIO into the new RustFS, then prove it.

One-off, for a dev machine that ran the stack before 05/10/2026 and has a
`devpath_minio_data` volume with objects in it (uploads, banners, transcripts,
certificate PDFs). How it was run, before switching the compose file over:

    docker run -d --name storage-migrate --network devpath_default \
        -v devpath_storage_data:/data \
        -e RUSTFS_ACCESS_KEY=devpath -e RUSTFS_SECRET_KEY=devpath-storage \
        rustfs/rustfs:1.0.1
    docker run --rm --network devpath_default -v <this dir>:/m:ro \
        devpath-backend:dev python /m/migrate_dev_bucket.py
    docker rm -f storage-migrate

then `docker compose up -d --remove-orphans`, which starts the `storage`
service on the volume just filled. Object by object through the S3 API: the
two servers' on-disk formats are not the same thing.
"""

import hashlib
import os
import time

import boto3
from botocore.config import Config


def client(endpoint: str, key: str, secret: str):
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=key,
        aws_secret_access_key=secret,
        region_name="auto",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


src = client(
    os.environ.get("SRC", "http://minio:9000"), "devpath", os.environ.get("SRC_SECRET", "devpath-minio")
)
dst = client(
    os.environ.get("DST", "http://storage-migrate:9000"),
    "devpath",
    os.environ.get("DST_SECRET", "devpath-storage"),
)

for _ in range(60):
    try:
        dst.list_buckets()
        break
    except Exception:  # noqa: BLE001 -- still starting
        time.sleep(1)


def objects(s3, bucket: str):
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        yield from page.get("Contents", [])


total_failed = 0
for bucket in [b["Name"] for b in src.list_buckets()["Buckets"]]:
    try:
        dst.create_bucket(Bucket=bucket)
    except dst.exceptions.ClientError as exc:
        if exc.response["Error"]["Code"] not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            raise

    copied = 0
    size = 0
    for item in objects(src, bucket):
        got = src.get_object(Bucket=bucket, Key=item["Key"])
        extra = {
            name: got[name]
            for name in ("ContentType", "CacheControl", "ContentDisposition", "ContentEncoding")
            if got.get(name)
        }
        dst.put_object(
            Bucket=bucket, Key=item["Key"], Body=got["Body"].read(), Metadata=got.get("Metadata", {}), **extra
        )
        copied += 1
        size += item["Size"]

    # Proof, not a count: every key on both sides, same bytes, same type.
    mismatched = []
    source = {o["Key"]: o["Size"] for o in objects(src, bucket)}
    target = {o["Key"]: o["Size"] for o in objects(dst, bucket)}
    if source != target:
        mismatched.append(f"key/size sets differ: {len(source)} vs {len(target)}")
    for key in source:
        a = src.get_object(Bucket=bucket, Key=key)
        b = dst.get_object(Bucket=bucket, Key=key)
        if hashlib.md5(a["Body"].read()).digest() != hashlib.md5(b["Body"].read()).digest():  # noqa: S324
            mismatched.append(f"{key}: bytes differ")
        elif a.get("ContentType") != b.get("ContentType"):
            mismatched.append(f"{key}: {a.get('ContentType')} != {b.get('ContentType')}")
    total_failed += len(mismatched)
    print(f"{bucket}: copied {copied} objects, {size} bytes; verified {len(source)} -> {len(mismatched)} mismatches")
    for line in mismatched[:20]:
        print("  " + line)

raise SystemExit(1 if total_failed else 0)
