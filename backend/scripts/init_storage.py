"""Create the media bucket on the self-hosted storage and say who may read it.

    python -m scripts.init_storage

Run by the one-shot `storage-init` service on every `docker compose up`
(infra/docker-compose.yml, infra/docker-compose.prod.yml), straight against
the RustFS server inside the compose network -- not through nginx, which
routes only the bucket's object paths. Idempotent: an existing bucket is kept,
and the policy and CORS rules are written again, so a value changed in the
compose file takes effect on the next `up`.

What it sets, and only this:

* anonymous `s3:GetObject` on the bucket's objects -- what a public R2 bucket
  gives the HLS player and `<img>`. Not `s3:ListBucket`: anybody could then
  walk the bucket, and certificate PDFs carry learners' names. Writes and
  deletes still need a signature (a presigned URL, or the app's own key).
* CORS only when STORAGE_CORS_ORIGINS is set. The dev stack needs it: the page
  at localhost:3000 PUTs uploads to minio.localhost:9000. Production serves
  the bucket on the site's own origin and sets none, so rules left over from
  an earlier value are removed rather than kept.

Environment: STORAGE_ENDPOINT, STORAGE_ACCESS_KEY, STORAGE_SECRET_KEY,
STORAGE_BUCKET, STORAGE_CORS_ORIGINS (comma-separated, may be empty).
Decision and measurements: docs/report/assets/phase-6/storage-decision.txt.
"""

import json
import os
import sys
import time
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

#: How long to keep trying while the server finishes starting. Compose waits
#: for its health check first, so this is a margin, not the main wait.
STARTUP_DEADLINE_SECONDS = 60


def public_read_policy(bucket: str) -> dict[str, Any]:
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "PublicReadObjects",
                "Effect": "Allow",
                "Principal": {"AWS": ["*"]},
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{bucket}/*"],
            }
        ],
    }


def cors_rules(origins: list[str]) -> list[dict[str, Any]]:
    """What a cross-origin page needs: PUT an upload to a presigned URL, and
    GET what it plays or draws. ETag exposed because a PUT's answer is read."""
    return [
        {
            "AllowedOrigins": origins,
            "AllowedMethods": ["GET", "HEAD", "PUT"],
            "AllowedHeaders": ["*"],
            "ExposeHeaders": ["ETag"],
            "MaxAgeSeconds": 3600,
        }
    ]


def parse_origins(raw: str) -> list[str]:
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def ensure_bucket(client: Any, bucket: str, origins: list[str]) -> list[str]:
    """Bring the bucket to the state above. Returns what it did, for the log."""
    done: list[str] = []
    # Asked first rather than read off create_bucket: RustFS answers 200 to
    # creating a bucket it already has, so "created" would be logged on every
    # `up` (seen 05/10 on a bucket holding 251 objects).
    try:
        client.head_bucket(Bucket=bucket)
        done.append(f"{bucket} already there")
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in ("404", "NoSuchBucket", "NotFound"):
            raise
        client.create_bucket(Bucket=bucket)
        done.append(f"created {bucket}")

    client.put_bucket_policy(Bucket=bucket, Policy=json.dumps(public_read_policy(bucket)))
    done.append("anonymous GetObject only")

    if origins:
        client.put_bucket_cors(Bucket=bucket, CORSConfiguration={"CORSRules": cors_rules(origins)})
        done.append(f"CORS for {', '.join(origins)}")
    else:
        try:
            client.delete_bucket_cors(Bucket=bucket)
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "NoSuchCORSConfiguration":
                raise
        done.append("no CORS (same origin)")
    return done


def main() -> int:
    env = os.environ
    client = boto3.client(
        "s3",
        endpoint_url=env["STORAGE_ENDPOINT"],
        aws_access_key_id=env["STORAGE_ACCESS_KEY"],
        aws_secret_access_key=env["STORAGE_SECRET_KEY"],
        region_name="auto",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    bucket = env.get("STORAGE_BUCKET") or "devpath-media"
    origins = parse_origins(env.get("STORAGE_CORS_ORIGINS", ""))

    deadline = time.monotonic() + STARTUP_DEADLINE_SECONDS
    while True:
        try:
            done = ensure_bucket(client, bucket, origins)
            break
        except (BotoCoreError, ClientError) as exc:
            if time.monotonic() > deadline:
                print(f"storage init failed: {exc}", file=sys.stderr)
                return 1
            time.sleep(2)

    print("storage init: " + "; ".join(done))
    return 0


if __name__ == "__main__":
    sys.exit(main())
