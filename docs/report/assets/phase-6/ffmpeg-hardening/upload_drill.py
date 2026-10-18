"""An honest video upload, end to end, after the hardening -- and the one name
the API now refuses.

Run inside the dev backend container, with the `worker` service restarted on
the code under test:

    docker compose exec -T backend python - < docs/report/assets/phase-6/ffmpeg-hardening/upload_drill.py

A throwaway @e2e instructor makes a draft course with one video lesson, asks
for a ticket, PUTs a real clip to the bucket, and waits for the transcode
worker. Removed afterwards by `scripts.purge_e2e`; the bucket objects are
deleted here.
"""

import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import httpx

from app.services.storage import asset_prefix, build_storage

API = "http://localhost:8000/api/v1"
http = httpx.Client(base_url=API, timeout=60)


def send(method: str, url: str, token: str | None = None, **kwargs):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = http.request(method, url, headers=headers, **kwargs)
    response.raise_for_status()
    return response.json() if response.content else None


email = f"video-{uuid.uuid4().hex[:8]}@e2e.devpath.example"
token = send("POST", "/auth/register",
             json={"email": email, "password": "devpath-video-drill", "full_name": "GV thử video"})["access_token"]
send("POST", "/users/me/instructor", token)
categories = send("GET", "/categories")
course = send("POST", "/courses", token, json={
    "title": f"Khóa thử video {uuid.uuid4().hex[:6]}", "category_id": categories[0]["id"],
    "subtitle": "Diễn tập gia cố ffmpeg", "description": "Tạm, sẽ gỡ.", "price": 0,
})
section = send("POST", f"/courses/{course['id']}/sections", token, json={"title": "Chương 1"})
lesson = send("POST", f"/sections/{section['id']}/lessons", token,
              json={"title": "Bài video", "type": "video"})
print(f"instructor {email}, lesson {lesson['id']}")

clip = Path(tempfile.mkdtemp()) / "bai-giang.mp4"
subprocess.run(
    ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=25:duration=14",
     "-f", "lavfi", "-i", "sine=frequency=440:duration=14", "-c:v", "libx264", "-preset", "ultrafast",
     "-c:a", "aac", str(clip)],
    check=True, timeout=120,
)
body = clip.read_bytes()

refused = http.post(f"/lessons/{lesson['id']}/video",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"filename": "bai-giang.m3u8", "content_type": "video/mp4", "size_bytes": len(body)})
print(f"ticket for 'bai-giang.m3u8' -> HTTP {refused.status_code}: "
      f"{refused.json()['detail']['errors'][0]['msg'] if refused.status_code == 422 else refused.text[:120]}")

ticket = send("POST", f"/lessons/{lesson['id']}/video", token,
              json={"filename": clip.name, "content_type": "video/mp4", "size_bytes": len(body)})
put = httpx.put(ticket["upload_url"], content=body, headers={"Content-Type": "video/mp4"}, timeout=120)
print(f"ticket for '{clip.name}' ({len(body):,} B) -> key {ticket['storage_key']}; PUT -> HTTP {put.status_code}")

send("POST", f"/video-assets/{ticket['video_asset_id']}/complete", token)
started = time.monotonic()
while True:
    asset = send("GET", f"/video-assets/{ticket['video_asset_id']}", token)
    if asset["status"] in ("ready", "failed") or time.monotonic() - started > 180:
        break
    time.sleep(1)
print(f"transcode -> {asset['status']} after {time.monotonic() - started:.1f} s, "
      f"duration {asset['duration_s']} s, error {asset['error_message']!r}")

if asset["status"] == "ready":
    storage = build_storage()
    prefix = asset_prefix(uuid.UUID(ticket["video_asset_id"]))
    manifest = storage.read_bytes(f"{prefix}/hls/index.m3u8").decode()
    segments = [line for line in manifest.splitlines() if line.endswith(".ts")]
    print(f"manifest in the bucket: {len(segments)} segments, VOD={'#EXT-X-PLAYLIST-TYPE:VOD' in manifest}")
    storage.delete_prefix(prefix + "/")
    print(f"deleted {prefix}/ from the bucket")
http.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
