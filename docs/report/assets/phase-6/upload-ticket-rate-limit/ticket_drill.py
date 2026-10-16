"""Ask for upload URLs until the API says 429, then watch the window end.

Talks HTTP to a running API -- the code under test -- and reads the same Redis
the API counts in. Run inside a backend container:

    docker compose exec -T backend python - < ticket_drill.py

Environment: API (default http://localhost:8000/api/v1); ADMIN_EMAIL and
ADMIN_PASSWORD for the banner step (skipped when unset). Redis comes from
REDIS_URL, which every backend container has.

Signs up one `@e2e.devpath.example` account and makes it an instructor with one
draft course; `python -m scripts.purge_e2e` removes both afterwards. Nothing is
uploaded: a ticket is only a signature, and what is under test is how many of
them one account is handed. The drill deletes its own lesson (and with it the
video row) and its Redis counters at the end.

  avatar   tickets until 429 -> the counter and its TTL in Redis -> DEL the
           counter (the "wait 24 h" shortcut) -> a ticket again
  video    1 MB tickets until 429 (the hourly count) -> EXPIRE the counter to
           3 s and sleep, so the window really ends on its own -> a ticket again;
           then 1.9 GB tickets until 429 (the 24 h byte budget) -> a 0.4 GB
           ticket still fits, because a refused ask is not spent
  banner   (admin) 25 tickets, all 200: deliberately not limited
"""

import os
import time
import uuid

import httpx
import redis

API = os.environ.get("API", "http://localhost:8000/api/v1")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
MB = 1024 * 1024
GB = 1024 * MB

store = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def until_refused(client, url, headers, body, *, most: int) -> tuple[int, httpx.Response]:
    """POST until the first non-2xx answer. Returns how many got through, and it."""
    for granted in range(most):
        response = client.post(url, json=body, headers=headers)
        if response.status_code >= 300:
            return granted, response
    raise SystemExit(f"FAIL  {most} tickets and no 429 -- the limit is not there")


def show_refusal(response: httpx.Response) -> None:
    detail = response.json()["detail"]
    print(f"      HTTP {response.status_code}  code={detail['code']}")
    print(f"      Retry-After: {response.headers.get('Retry-After')}  "
          f"retry_after={detail.get('retry_after')}")
    print(f"      message: {detail['message']}")


def show_key(key: str) -> None:
    print(f"      redis {key}: value={store.get(key)} ttl={store.ttl(key)} s")


def check(label: str, ok: bool, results: list) -> None:
    results.append(ok)
    print(f"  {'PASS' if ok else 'FAIL'}  {label}")


def main() -> None:
    results: list[bool] = []
    client = httpx.Client(timeout=30)
    email = f"ve-tai-len-{uuid.uuid4().hex[:8]}@e2e.devpath.example"
    signed_up = client.post(
        f"{API}/auth/register",
        json={"email": email, "password": "mat-khau-thu-ve", "full_name": "Thử vé tải lên"},
    )
    signed_up.raise_for_status()
    user_id = signed_up.json()["user"]["id"]
    headers = bearer(signed_up.json()["access_token"])
    print(f"account {email} ({user_id})\n")

    # --- avatar --------------------------------------------------------------
    print("[avatar] POST /users/me/avatar, 200 KB PNG, until refused")
    avatar = {"filename": "anh.png", "content_type": "image/png", "size_bytes": 200 * 1024}
    granted, refused = until_refused(
        client, f"{API}/users/me/avatar", headers, avatar, most=100
    )
    print(f"      {granted} x 201, then:")
    show_refusal(refused)
    avatar_key = f"upload:avatar:user:{user_id}"
    show_key(avatar_key)
    check("avatar: 20 tickets, the 21st is 429 UPLOAD_RATE_LIMITED",
          granted == 20 and refused.status_code == 429
          and refused.json()["detail"]["code"] == "UPLOAD_RATE_LIMITED", results)
    check("avatar: Retry-After within the 24 h window",
          0 < int(refused.headers["Retry-After"]) <= 24 * 3600, results)
    again = client.post(f"{API}/users/me/avatar", json=avatar, headers=headers)
    check(f"avatar: still refused before the window ends ({again.status_code})",
          again.status_code == 429, results)
    store.delete(avatar_key)
    print(f"      DEL {avatar_key}")
    again = client.post(f"{API}/users/me/avatar", json=avatar, headers=headers)
    check(f"avatar: counter gone -> a ticket again ({again.status_code})",
          again.status_code == 201, results)
    print()

    # --- video ---------------------------------------------------------------
    client.post(f"{API}/users/me/instructor", headers=headers).raise_for_status()
    category = client.get(f"{API}/categories").json()[0]["id"]
    course = client.post(
        f"{API}/courses", json={"title": "Khóa thử vé tải lên", "category_id": category},
        headers=headers,
    )
    course.raise_for_status()
    section = client.post(
        f"{API}/courses/{course.json()['id']}/sections", json={"title": "Chương 1"},
        headers=headers,
    )
    lesson = client.post(
        f"{API}/sections/{section.json()['id']}/lessons",
        json={"title": "Bài video", "type": "video"}, headers=headers,
    )
    lesson.raise_for_status()
    lesson_id = lesson.json()["id"]
    video_url = f"{API}/lessons/{lesson_id}/video"

    def video(size: int) -> dict:
        return {"filename": "bai-giang.mp4", "content_type": "video/mp4", "size_bytes": size}

    print("[video] POST /lessons/{id}/video, 1 MB, until refused (hourly count)")
    started = time.monotonic()
    granted, refused = until_refused(client, video_url, headers, video(MB), most=200)
    print(f"      {granted} x 201 in {time.monotonic() - started:.1f} s, then:")
    show_refusal(refused)
    count_key = f"upload:video:user:{user_id}"
    bytes_key = f"upload:video-bytes:user:{user_id}"
    show_key(count_key)
    show_key(bytes_key)
    check("video: 60 tickets in the hour, the 61st is 429",
          granted == 60 and refused.status_code == 429, results)
    check("video: the refused ticket spent no bytes (60 x 1 MB on the budget)",
          int(store.get(bytes_key)) == 60 * MB, results)

    store.expire(count_key, 3)
    print(f"      EXPIRE {count_key} 3, sleep 4 s")
    time.sleep(4)
    print(f"      redis {count_key}: exists={store.exists(count_key)}")
    again = client.post(video_url, json=video(MB), headers=headers)
    check(f"video: the hour ran out on its own -> a ticket again ({again.status_code})",
          again.status_code == 201, results)
    store.delete(count_key)
    print()

    print("[video] 1.9 GB tickets until refused (24 h byte budget, 10 GB)")
    big = int(1.9 * GB)
    granted, refused = until_refused(client, video_url, headers, video(big), most=20)
    print(f"      {granted} x 201, then:")
    show_refusal(refused)
    show_key(bytes_key)
    spent = int(store.get(bytes_key))
    check(f"video: 5 x 1.9 GB granted, the 6th refused (spent {spent / GB:.2f} GB)",
          granted == 5 and refused.status_code == 429, results)
    fits = client.post(video_url, json=video(int(0.4 * GB)), headers=headers)
    show_key(bytes_key)
    check(f"video: 0.4 GB still fits after the refusal ({fits.status_code})",
          fits.status_code == 201, results)

    client.delete(f"{API}/lessons/{lesson_id}", headers=headers).raise_for_status()
    store.delete(count_key, bytes_key)
    print(f"      DELETE /lessons/{lesson_id} (and its video row); DEL counters\n")

    # --- banner --------------------------------------------------------------
    if ADMIN_EMAIL and ADMIN_PASSWORD:
        print("[banner] POST /admin/banners/upload-url as admin, 8 MB, 25 times")
        admin = httpx.Client(timeout=30)
        signed_in = admin.post(
            f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        signed_in.raise_for_status()
        admin_headers = bearer(signed_in.json()["access_token"])
        banner = {"filename": "tet.png", "content_type": "image/png", "size_bytes": 8 * MB}
        statuses = [
            admin.post(f"{API}/admin/banners/upload-url", json=banner,
                       headers=admin_headers).status_code
            for _ in range(25)
        ]
        admin.post(f"{API}/auth/logout")
        print(f"      statuses: {sorted(set(statuses))} x {len(statuses)}; signed out")
        check("banner: 25 x 200, not limited", statuses == [200] * 25, results)
        print()

    print(f"{sum(results)}/{len(results)}")


main()
