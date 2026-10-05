"""The dev stack's storage, end to end as a browser uses it.

Runs inside the backend container (`docker compose exec -T backend python -
< dev_smoke.py`), where `minio.localhost` is the storage service's alias --
the same name, and so the same signed URL, the browser on the host uses.

A throwaway `@e2e.devpath.example` account (`scripts.purge_e2e` removes it):
ask the API for an avatar upload URL, PUT the picture to it the way the page
does (with the page's Origin, so CORS is exercised), confirm, then read the
avatar back anonymously. Plus what an anonymous visitor must not be able to
do, and the CORS answer for an origin that is not the page.
"""

import os
import uuid

import httpx

API = "http://localhost:8000/api/v1"
PAGE = "http://localhost:3000"
BUCKET_URL = "http://minio.localhost:9000/devpath-media"
failures = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global failures
    failures += 0 if ok else 1
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""), flush=True)


with httpx.Client(timeout=30) as http:
    email = f"storage-smoke-{uuid.uuid4().hex[:10]}@e2e.devpath.example"
    signed_up = http.post(
        f"{API}/auth/register",
        json={"email": email, "password": "storage-smoke-password", "full_name": "Storage Smoke"},
    )
    token = signed_up.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    picture = os.urandom(50_000)
    ticket = http.post(
        f"{API}/users/me/avatar",
        json={"filename": "me.png", "content_type": "image/png", "size_bytes": len(picture)},
        headers=auth,
    ).json()
    check("upload URL points at the bucket's public name", ticket["upload_url"].startswith(BUCKET_URL + "/"))

    preflight = http.request(
        "OPTIONS",
        ticket["upload_url"],
        headers={"Origin": PAGE, "Access-Control-Request-Method": "PUT", "Access-Control-Request-Headers": "content-type"},
    )
    check(
        "CORS preflight from the page",
        preflight.status_code == 200 and preflight.headers.get("access-control-allow-origin") == PAGE,
        f"HTTP {preflight.status_code}, allow-origin {preflight.headers.get('access-control-allow-origin')}",
    )

    put = http.put(ticket["upload_url"], content=picture, headers={"Content-Type": "image/png", "Origin": PAGE})
    check("PUT to the presigned URL", put.status_code == 200, f"HTTP {put.status_code}")

    confirmed = http.post(f"{API}/users/me/avatar/complete", json={"storage_key": ticket["storage_key"]}, headers=auth)
    avatar_url = confirmed.json().get("avatar_url") or ""
    check("API accepts the uploaded avatar", confirmed.status_code == 200 and avatar_url.startswith(BUCKET_URL), avatar_url)

    shown = http.get(avatar_url, headers={"Origin": PAGE})
    check(
        "anonymous GET of the avatar",
        shown.status_code == 200 and shown.content == picture and shown.headers.get("content-type") == "image/png",
        f"HTTP {shown.status_code}, {shown.headers.get('content-type')}",
    )

    for listing in (f"{BUCKET_URL}?list-type=2", f"{BUCKET_URL}/"):
        r = http.get(listing)
        check(f"anonymous listing refused: {listing.removeprefix(BUCKET_URL) or '/'}", r.status_code == 403, f"HTTP {r.status_code}")

    r = http.put(f"{BUCKET_URL}/avatars/forged.png", content=b"x", headers={"Content-Type": "image/png"})
    check("unsigned PUT refused", r.status_code == 403, f"HTTP {r.status_code}")
    r = http.delete(avatar_url)
    check("unsigned DELETE refused", r.status_code == 403, f"HTTP {r.status_code}")

    evil = http.request(
        "OPTIONS",
        ticket["upload_url"],
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "PUT"},
    )
    check(
        "CORS preflight from another origin refused",
        evil.headers.get("access-control-allow-origin") is None,
        f"HTTP {evil.status_code}",
    )

print(f"\n{failures} failed")
raise SystemExit(failures)
