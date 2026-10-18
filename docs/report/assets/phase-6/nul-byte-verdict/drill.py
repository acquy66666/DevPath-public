"""A real submission that prints a NUL byte, through the real worker and sandbox.

Run inside the dev backend container, against the API it serves, after
restarting `grading-worker` on the code under test:

    docker compose exec -T backend python - < docs/report/assets/phase-6/nul-byte-verdict/drill.py

A throwaway @e2e.devpath.example student enrols in the seeded free Python
course and submits to its code exercise (2 sample cases, 4 hidden). Afterwards:
`docker compose exec backend python -m scripts.purge_e2e`.
"""

import asyncio
import time
import uuid

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings

API = "http://localhost:8000/api/v1"
COURSE_SLUG = "python-co-ban-cho-nguoi-moi-bat-dau"

# Reads both input lines, then prints `3` followed by a NUL byte. The source
# holds the two characters `\0`, not a NUL itself: only the output has one.
# A wrong answer on both sample cases (they expect "3" and "0"), nothing more.
PRINTS_NUL = 'input()\ninput()\nprint(3, end="\\0\\n")\n'


def query(sql: str, **params):
    """One read, with the app's own driver. Nothing here writes."""

    async def run():
        engine = create_async_engine(get_settings().database_url)
        async with engine.connect() as db:
            row = (await db.execute(text(sql), params)).one()
        await engine.dispose()
        return row

    return asyncio.run(run())


course_id, exercise_id = query(
    "select c.id, ce.id from code_exercises ce"
    " join lessons l on l.id = ce.lesson_id"
    " join course_sections s on s.id = l.section_id"
    " join courses c on c.id = s.course_id where c.slug = :slug",
    slug=COURSE_SLUG,
)

http = httpx.Client(base_url=API, timeout=30)
email = f"nul-{uuid.uuid4().hex[:8]}@e2e.devpath.example"
password = "devpath-nul-drill"
http.post("/auth/register", json={"email": email, "password": password, "full_name": "Thử NUL"}).raise_for_status()
token = http.post("/auth/login", json={"email": email, "password": password}).json()["access_token"]
auth = {"Authorization": f"Bearer {token}"}
http.post(f"/courses/{course_id}/enroll", headers=auth).raise_for_status()
print(f"student {email}, exercise {exercise_id}")

# 1. Code that itself contains a NUL: refused at the door, or not.
raw = http.post(
    f"/code-exercises/{exercise_id}/submissions", json={"code": "print(1)\x00"}, headers=auth
)
print(f"code containing a NUL byte -> HTTP {raw.status_code}")
if raw.status_code != 422:
    # It got past validation, so it counted against the per-exercise cooldown
    # (SUBMISSION_COOLDOWN_SECONDS, 10 s on dev) before the insert failed.
    time.sleep(get_settings().submission_cooldown_seconds + 1)

# 2. A program that prints one.
started = time.monotonic()
submitted = http.post(
    f"/code-exercises/{exercise_id}/submissions", json={"code": PRINTS_NUL}, headers=auth
)
submitted.raise_for_status()
submission_id = submitted.json()["id"]
while True:
    detail = http.get(f"/submissions/{submission_id}", headers=auth).json()
    if detail["status"] in ("done", "error"):
        break
    if time.monotonic() - started > 240:
        print("still not finished after 240 s")
        break
    time.sleep(1)
elapsed = time.monotonic() - started

print(f"program printing a NUL -> status {detail['status']}, verdict {detail['verdict']}, "
      f"score {detail['score']}, after {elapsed:.1f} s")
print(f"  message: {detail['message']!r}")
for result in detail.get("results", []):
    shown = result.get("stdout_trunc")
    print(f"  case {result.get('position')}: {result['verdict']}"
          + (f", stdout shown to the student: {shown!r}" if shown is not None else ", hidden"))

(attempts,) = query(
    "select count(*) from submission_results where submission_id = :id", id=submission_id
)
print(f"  rows in submission_results: {attempts}")
http.post("/auth/logout", headers=auth)
