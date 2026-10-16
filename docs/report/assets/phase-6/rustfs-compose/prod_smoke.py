"""The production stack's storage, end to end, through its real nginx.

Run inside the production backend container of a stack built from
infra/docker-compose.prod.yml (`docker compose ... exec -T backend python -
< prod_smoke.py`). Inside that network ${DOMAIN} is an alias of nginx, so
every request here -- the API's own S3 calls and the "browser" ones made with
httpx -- goes https://${DOMAIN} -> nginx -> TLS -> the `storage` service, as
on the server. AWS_CA_BUNDLE names the certificate to trust (a self-signed one
on the dev machine; Let's Encrypt's needs none).

A throwaway `@e2e.devpath.example` account: avatar upload through the API,
then what anonymous visitors may and may not do, the headers nginx puts on
uploaded content, and the app's own bucket calls (multipart upload, list,
delete) as the transcode worker makes them.
"""

import os
import tempfile
import uuid

import httpx

from app.core.config import get_settings
from app.services.storage import build_storage

settings = get_settings()
SITE = settings.frontend_url  # https://${DOMAIN}
BUCKET_URL = settings.r2_public_base_url
CA = os.environ["AWS_CA_BUNDLE"]
MB = 1024 * 1024
failures = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global failures
    failures += 0 if ok else 1
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""), flush=True)


print(f"site {SITE}, bucket {BUCKET_URL}, endpoint {settings.r2_endpoint_url}")
check("the app signs for the site's own origin", BUCKET_URL == f"{SITE}/devpath-media")

with httpx.Client(verify=CA, timeout=120) as http:
    email = f"storage-smoke-{uuid.uuid4().hex[:10]}@e2e.devpath.example"
    signed_up = http.post(
        f"{SITE}/api/v1/auth/register",
        json={"email": email, "password": "storage-smoke-password", "full_name": "Storage Smoke"},
    )
    check("sign-up through nginx", signed_up.status_code == 201, f"HTTP {signed_up.status_code}")
    auth = {"Authorization": f"Bearer {signed_up.json()['access_token']}"}

    picture = os.urandom(50_000)
    ticket = http.post(
        f"{SITE}/api/v1/users/me/avatar",
        json={"filename": "me.png", "content_type": "image/png", "size_bytes": len(picture)},
        headers=auth,
    ).json()
    check("upload URL is on the site's origin", ticket["upload_url"].startswith(BUCKET_URL + "/"))

    put = http.put(ticket["upload_url"], content=picture, headers={"Content-Type": "image/png", "Origin": SITE})
    check("same-origin PUT to the presigned URL", put.status_code == 200, f"HTTP {put.status_code}")

    confirmed = http.post(
        f"{SITE}/api/v1/users/me/avatar/complete", json={"storage_key": ticket["storage_key"]}, headers=auth
    )
    avatar_url = confirmed.json().get("avatar_url") or ""
    check("API accepts the avatar", confirmed.status_code == 200 and avatar_url.startswith(BUCKET_URL), avatar_url)

    shown = http.get(avatar_url)
    check(
        "anonymous GET of the avatar",
        shown.status_code == 200 and shown.content == picture and shown.headers.get("content-type") == "image/png",
        f"HTTP {shown.status_code}, {shown.headers.get('content-type')}",
    )
    policies = shown.headers.get_list("content-security-policy")
    check("uploaded content is sandboxed", any(p.startswith("sandbox") for p in policies), " | ".join(policies))
    check("nosniff on uploaded content", shown.headers.get("x-content-type-options") == "nosniff")
    check("HSTS on uploaded content", "max-age=" in shown.headers.get("strict-transport-security", ""))

    ranged = http.get(avatar_url, headers={"Range": "bytes=0-1023"})
    check("Range request", ranged.status_code == 206 and len(ranged.content) == 1024, f"HTTP {ranged.status_code}")

    for listing in (f"{BUCKET_URL}?list-type=2", f"{BUCKET_URL}/"):
        r = http.get(listing)
        check(f"anonymous listing refused: {listing.removeprefix(BUCKET_URL)}", r.status_code == 403, f"HTTP {r.status_code}")
    r = http.put(f"{BUCKET_URL}/avatars/forged.png", content=b"x", headers={"Content-Type": "image/png"})
    check("unsigned PUT refused", r.status_code == 403, f"HTTP {r.status_code}")
    r = http.delete(avatar_url)
    check("unsigned DELETE refused", r.status_code == 403, f"HTTP {r.status_code}")
    r = http.put(f"{SITE}/devpath-backups", content=b"")
    check(
        "no other bucket is routed (create attempt lands on the app)",
        "<Error>" not in r.text and r.status_code != 200,
        f"HTTP {r.status_code}",
    )

    # Through nginx at upload size: the 2m limit of the rest of the site would
    # refuse this; the media location streams it.
    storage = build_storage()
    key = f"videos/smoke-{uuid.uuid4().hex[:8]}/original.mp4"
    big = os.urandom(100 * MB)
    r = http.put(
        storage.presigned_put_url(key, "video/mp4", 600, size_bytes=len(big)),
        content=big,
        headers={"Content-Type": "video/mp4"},
    )
    check("100 MB PUT through nginx", r.status_code == 200, f"HTTP {r.status_code}")

# --- The app's own calls, as the transcode worker makes them ---------------

prefix = key.rsplit("/", 1)[0] + "/"
with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "original.mp4")
    storage.download_file(key, path)
    check("download_file", os.path.getsize(path) == 100 * MB)
    segment = os.path.join(tmp, "seg0.ts")
    with open(segment, "wb") as handle:
        handle.write(os.urandom(20 * MB))
    storage.upload_file(segment, prefix + "hls/seg0.ts")
    check("upload_file, multipart", True)
storage.upload_bytes(b"%PDF-1.7 smoke", prefix + "cert.pdf", "application/pdf")
check("upload_bytes + read_bytes", storage.read_bytes(prefix + "cert.pdf") == b"%PDF-1.7 smoke")
listed = sorted(obj.key for obj in storage.list_objects(prefix))
check("list_objects", len(listed) == 3, f"{len(listed)} objects")
refused = storage.delete_keys(listed)
check("delete_keys", refused == [] and list(storage.list_objects(prefix)) == [])
storage.delete_prefix(f"avatars/{confirmed.json()['id']}/")

print(f"\n{failures} failed")
raise SystemExit(failures)
