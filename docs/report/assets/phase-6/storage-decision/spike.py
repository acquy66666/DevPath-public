"""The app's storage adapter against a self-hosted S3 server behind nginx.

Everything the app does with a bucket is done here by the app's own code --
`app.services.storage.R2Storage`, with boto3 exactly as locked -- through an
nginx that forwards /devpath-media to the server the way a production nginx
would: same origin as the site, TLS, Host passed through because SigV4 signs
it. The browser's half (a PUT to a presigned URL, a GET of a public URL) is
done with httpx, the way `fetch` would do it.

Run by run.sh; one line per check, exit status = number of failures.
"""

import hashlib
import json
import os
import tempfile
import time
import uuid

import boto3
import httpx
from botocore.config import Config

from app.services.storage import R2Storage

FRONT = "https://spike-front"
BUCKET = "devpath-media"
ACCESS = "spikeaccess"
SECRET = "spike-secret-0123456789"
CANDIDATE = os.environ["CANDIDATE"]
MB = 1024 * 1024

failures = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global failures
    failures += 0 if ok else 1
    suffix = f"  ({detail})" if detail else ""
    print(f"{'PASS' if ok else 'FAIL'}  {name}{suffix}", flush=True)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


# --- The bucket, set up the way an init step would, straight to the server -

admin = boto3.client(
    "s3",
    endpoint_url=os.environ["ADMIN_ENDPOINT"],
    aws_access_key_id=ACCESS,
    aws_secret_access_key=SECRET,
    region_name="auto",
    config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
)
for _ in range(90):
    try:
        admin.list_buckets()
        break
    except Exception:  # noqa: BLE001 -- the server is still starting
        time.sleep(1)
admin.create_bucket(Bucket=BUCKET)
if CANDIDATE == "rustfs":
    # Anonymous GetObject and nothing else: no ListBucket, so the bucket
    # cannot be walked (certificate PDFs carry learners' names).
    admin.put_bucket_policy(
        Bucket=BUCKET,
        Policy=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": ["*"]},
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{BUCKET}/*"],
                    }
                ],
            }
        ),
    )
# SeaweedFS: anonymous Read on this bucket comes from seaweedfs-s3.json.

storage = R2Storage(
    endpoint_url=FRONT,
    access_key_id=ACCESS,
    secret_access_key=SECRET,
    bucket=BUCKET,
    public_base_url=f"{FRONT}/{BUCKET}",
)
browser = httpx.Client(verify=os.environ["AWS_CA_BUNDLE"], timeout=120)
run = uuid.uuid4().hex[:8]

# --- Browser: presigned upload, public read --------------------------------

avatar_key = f"avatars/{run}/a.png"
avatar = os.urandom(200_000)
url = storage.presigned_put_url(avatar_key, "image/png", 600, size_bytes=len(avatar))
check("presigned URL is path-style on the site's own origin", url.startswith(f"{FRONT}/{BUCKET}/"), url.split("?")[0])

r = browser.put(url, content=avatar, headers={"Content-Type": "image/png"})
check("browser PUT to the presigned URL", r.status_code == 200, f"HTTP {r.status_code}")

r = browser.put(url, content=avatar, headers={"Content-Type": "text/html"})
check("same URL with another Content-Type is refused", r.status_code == 403, f"HTTP {r.status_code}")

r = browser.put(url, content=avatar + b"x", headers={"Content-Type": "image/png"})
check("same URL with one byte more is refused", r.status_code == 403, f"HTTP {r.status_code}")

r = browser.put(f"{FRONT}/{BUCKET}/avatars/{run}/forged.png", content=b"x", headers={"Content-Type": "image/png"})
check("unsigned PUT is refused", r.status_code == 403, f"HTTP {r.status_code}")

r = browser.delete(storage.public_url(avatar_key))
check("unsigned DELETE is refused", r.status_code == 403, f"HTTP {r.status_code}")

r = browser.get(storage.public_url(avatar_key))
check(
    "anonymous GET of the public URL",
    r.status_code == 200 and sha(r.content) == sha(avatar),
    f"HTTP {r.status_code}, {r.headers.get('content-type')}",
)
check("Content-Type kept from the signed upload", r.headers.get("content-type") == "image/png", r.headers.get("content-type", ""))

r = browser.get(storage.public_url(avatar_key), headers={"Range": "bytes=0-1023"})
check("Range request (video players seek)", r.status_code == 206 and len(r.content) == 1024, f"HTTP {r.status_code}, {len(r.content)} B")

for listing in (f"{FRONT}/{BUCKET}?list-type=2", f"{FRONT}/{BUCKET}/"):
    r = browser.get(listing)
    leaked = avatar_key in r.text
    check(f"anonymous listing refused: GET {listing.removeprefix(FRONT)}", r.status_code == 403 and not leaked, f"HTTP {r.status_code}")

r = browser.get(storage.public_url(f"avatars/{run}/missing.png"))
check("missing key is not a 200", r.status_code in (403, 404), f"HTTP {r.status_code}")

big = os.urandom(60 * MB)
url = storage.presigned_put_url(f"videos/{run}/original.mp4", "video/mp4", 600, size_bytes=len(big))
started = time.perf_counter()
r = browser.put(url, content=big, headers={"Content-Type": "video/mp4"})
check("60 MB original video through nginx", r.status_code == 200, f"HTTP {r.status_code}, {time.perf_counter() - started:.1f} s")

# --- Workers and API: the adapter's own calls ------------------------------

with tempfile.TemporaryDirectory() as tmp:
    original = os.path.join(tmp, "original.mp4")
    storage.download_file(f"videos/{run}/original.mp4", original)
    with open(original, "rb") as handle:
        check("download_file (transcode worker)", sha(handle.read()) == sha(big))

    segment = os.urandom(20 * MB)
    seg_path = os.path.join(tmp, "seg0.ts")
    with open(seg_path, "wb") as handle:
        handle.write(segment)
    try:
        storage.upload_file(seg_path, f"videos/{run}/hls/seg0.ts")
        check("upload_file, 20 MB = multipart (HLS output)", True)
    except Exception as exc:  # noqa: BLE001
        check("upload_file, 20 MB = multipart (HLS output)", False, repr(exc)[:200])

    playlist = os.path.join(tmp, "index.m3u8")
    with open(playlist, "w") as handle:
        handle.write("#EXTM3U\n#EXT-X-VERSION:3\nseg0.ts\n#EXT-X-ENDLIST\n")
    storage.upload_file(playlist, f"videos/{run}/hls/index.m3u8")

r = browser.get(storage.public_url(f"videos/{run}/hls/index.m3u8"))
check("playlist served with a playlist type", r.status_code == 200 and "mpegurl" in r.headers.get("content-type", ""), r.headers.get("content-type", ""))
r = browser.get(storage.public_url(f"videos/{run}/hls/seg0.ts"))
check("segment served whole", r.status_code == 200 and sha(r.content) == sha(segment), f"{len(r.content)} B")

try:
    storage.upload_bytes("1\n00:00:01,000 --> 00:00:02,000\nXin chào\n".encode(), f"videos/{run}/transcript.srt", "application/x-subrip")
    back = storage.read_bytes(f"videos/{run}/transcript.srt").decode()
    check("upload_bytes + read_bytes (transcript)", "Xin chào" in back)
except Exception as exc:  # noqa: BLE001
    check("upload_bytes + read_bytes (transcript)", False, repr(exc)[:200])

listed = {obj.key: obj.size for obj in storage.list_objects(f"videos/{run}/")}
expected = {
    f"videos/{run}/original.mp4": 60 * MB,
    f"videos/{run}/hls/seg0.ts": 20 * MB,
}
check(
    "list_objects (orphan sweep)",
    all(listed.get(k) == v for k, v in expected.items()) and len(listed) == 4,
    f"{len(listed)} objects",
)

try:
    refused = storage.delete_keys(sorted(listed))
    left = list(storage.list_objects(f"videos/{run}/"))
    check("delete_keys = DeleteObjects (orphan sweep)", refused == [] and left == [], f"refused {refused}, left {len(left)}")
except Exception as exc:  # noqa: BLE001
    check("delete_keys = DeleteObjects (orphan sweep)", False, repr(exc)[:200])

try:
    storage.delete_prefix(f"avatars/{run}/")
    check("delete_prefix (avatar replaced)", list(storage.list_objects(f"avatars/{run}/")) == [])
except Exception as exc:  # noqa: BLE001
    check("delete_prefix (avatar replaced)", False, repr(exc)[:200])

print(f"\n{CANDIDATE}: {failures} failed")
raise SystemExit(failures)
