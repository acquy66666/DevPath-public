"""Does the bucket hold a signed Content-Length? Asked of the real server.

Run inside the backend container, so the URL is signed by the app's own
boto3 client (the locked version) for the host the browser would use:

    docker compose exec -T backend python - < docs/report/assets/phase-6/signed-upload-length/probe.py

Every case PUTs to a fresh key and then asks the bucket, with the app's own
credentials, whether an object landed and how big it is. Nothing is left
behind: each key is deleted at the end, whatever happened.
"""

import time
import uuid

import httpx
from botocore.exceptions import ClientError

from app.core.config import get_settings
from app.services.storage import build_storage

storage = build_storage()
client = storage._client  # the experiment needs both the old and the new signing
bucket = get_settings().r2_bucket
run = uuid.uuid4().hex[:8]
keys: list[str] = []
failures = 0

MB = 1024 * 1024
SIGNED = 1024  # what the ticket declares


def sign(key: str, length: int | None) -> str:
    params = {"Bucket": bucket, "Key": key, "ContentType": "image/png"}
    if length is not None:
        params["ContentLength"] = length
    return client.generate_presigned_url("put_object", Params=params, ExpiresIn=600)


def stored_size(key: str) -> int | None:
    try:
        return client.head_object(Bucket=bucket, Key=key)["ContentLength"]
    except ClientError:
        return None


def body(size: int, chunk: int = MB):
    sent = 0
    while sent < size:
        piece = min(chunk, size - sent)
        sent += piece
        yield b"\0" * piece


def put(url: str, size: int, *, chunked: bool = False, content_type: str = "image/png"):
    headers = {"Content-Type": content_type}
    if chunked:
        content = body(size)  # no length known -> Transfer-Encoding: chunked
    else:
        headers["Content-Length"] = str(size)
        content = body(size)
    started = time.monotonic()
    try:
        response = httpx.put(url, content=content, headers=headers, timeout=120)
        outcome = f"HTTP {response.status_code}"
        if response.status_code >= 400 and b"<Code>" in response.content:
            code = response.content.split(b"<Code>")[1].split(b"</Code>")[0].decode()
            outcome += f" {code}"
    except httpx.HTTPError as exc:
        outcome = f"connection ended: {type(exc).__name__}"
    return outcome, time.monotonic() - started


def case(label: str, *, signed: int | None, size: int, expect_status: str,
         expect_stored: int | None, **put_kwargs) -> None:
    global failures
    key = f"avatars/probe-{run}/{len(keys):02d}.png"
    keys.append(key)
    outcome, elapsed = put(sign(key, signed), size, **put_kwargs)
    landed = stored_size(key)
    ok = outcome.startswith(expect_status) and landed == expect_stored
    failures += not ok
    signed_text = "unsigned" if signed is None else f"signed {signed} B"
    print(
        f"{'PASS' if ok else 'FAIL'}  {label:<44} {signed_text:<14} body {size:>11,} B  "
        f"-> {outcome:<34} stored: {landed if landed is not None else 'nothing'}  ({elapsed:.2f} s)"
    )


print(f"bucket {bucket} via {client.meta.endpoint_url}, run {run}")
print()
print("Control -- signed without the length, as the app did until 16/10/2026:")
case("declares 1 KB, sends 20 MB", signed=None, size=20 * MB,
     expect_status="HTTP 200", expect_stored=20 * MB)
print()
print("With Content-Length in the signature:")
case("sends exactly what was signed", signed=SIGNED, size=SIGNED,
     expect_status="HTTP 200", expect_stored=SIGNED)
case("one byte more", signed=SIGNED, size=SIGNED + 1,
     expect_status="HTTP 403", expect_stored=None)
case("one byte less", signed=SIGNED, size=SIGNED - 1,
     expect_status="HTTP 403", expect_stored=None)
case("20 MB", signed=SIGNED, size=20 * MB,
     expect_status="HTTP 403", expect_stored=None)
case("chunked, no Content-Length, right size", signed=SIGNED, size=SIGNED,
     expect_status="HTTP 4", expect_stored=None, chunked=True)
case("chunked, no Content-Length, 20 MB", signed=SIGNED, size=20 * MB,
     expect_status="HTTP 4", expect_stored=None, chunked=True)
case("right size, other Content-Type", signed=SIGNED, size=SIGNED,
     expect_status="HTTP 403", expect_stored=None, content_type="text/html")
print()
print("Does the bucket read the whole body before refusing? (500 MB against a 1 KB ticket)")
case("500 MB", signed=SIGNED, size=500 * MB,
     expect_status="", expect_stored=None)

for key in keys:
    client.delete_object(Bucket=bucket, Key=key)
left = [key for key in keys if stored_size(key) is not None]
print()
print(f"cleanup: {len(keys)} keys deleted, {len(left)} left")
print(f"{len(keys) - failures}/{len(keys)} as expected")
raise SystemExit(1 if failures or left else 0)
