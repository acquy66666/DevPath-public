"""Sign the browser's tickets, then ask the bucket what landed.

Runs inside the dev backend container, so the URLs are signed by the app's own
`R2Storage` (and the boto3 it locks), for https://devpath.localhost -- the
name the nginx of run.sh answers to:

    python - sign <run> < tickets.py     prints the cases as JSON
    python - check <run> < tickets.py    HEADs every key, deletes it, exit 1 on a surprise
"""

import json
import sys

from botocore.exceptions import ClientError

from app.core.config import get_settings
from app.services.storage import R2Storage, build_storage

MB = 1024 * 1024
SITE = "https://devpath.localhost"

mode, run = sys.argv[1], sys.argv[2]
settings = get_settings()
storage = R2Storage(
    endpoint_url=SITE,
    access_key_id=settings.r2_access_key_id,
    secret_access_key=settings.r2_secret_access_key,
    bucket=settings.r2_bucket,
    public_base_url=f"{SITE}/{settings.r2_bucket}",
)

# (label, size the ticket declares or None for the old unsigned URL, bytes the
#  browser sends, HTTP status expected, size expected in the bucket)
CASES = [
    ("exact size, 1 MB", 1 * MB, 1 * MB, 200, 1 * MB),
    ("one byte more than signed", 1 * MB, 1 * MB + 1, 403, None),
    ("one byte less than signed", 1 * MB, 1 * MB - 1, 403, None),
    ("50 MB on a 1 MB ticket", 1 * MB, 50 * MB, 403, None),
    ("exact size, 50 MB", 50 * MB, 50 * MB, 200, 50 * MB),
    ("control: old unsigned URL, 50 MB", None, 50 * MB, 200, 50 * MB),
]


def key(index: int) -> str:
    return f"videos/upload-probe-{run}/{index:02d}.mp4"


if mode == "sign":
    cases = []
    for index, (label, signed, sent, status, _) in enumerate(CASES):
        if signed is None:
            # How the app signed before this change, kept as the control.
            url = storage._client.generate_presigned_url(
                "put_object",
                Params={"Bucket": storage._bucket, "Key": key(index), "ContentType": "video/mp4"},
                ExpiresIn=600,
            )
        else:
            url = storage.presigned_put_url(key(index), "video/mp4", 600, size_bytes=signed)
        cases.append(
            {"label": label, "signed": signed, "bytes": sent, "expect": status, "url": url}
        )
    print(json.dumps(cases))
    sys.exit(0)

# Asked through the app's own endpoint: devpath.localhost is the host's
# nginx, which the container cannot reach. Same bucket either way.
inside = build_storage()._client
surprises = 0
for index, (label, _, _, _, expected) in enumerate(CASES):
    try:
        landed = inside.head_object(Bucket=storage._bucket, Key=key(index))["ContentLength"]
    except ClientError:
        landed = None
    ok = landed == expected
    surprises += not ok
    print(f"{'PASS' if ok else 'FAIL'}  bucket holds for {label!r}: {landed if landed is not None else 'nothing'}")
    inside.delete_object(Bucket=storage._bucket, Key=key(index))
sys.exit(1 if surprises else 0)
