"""Outside the grader: does a NUL in other free-text fields still reach Postgres?

Measures only -- this task fixes the grading subsystem, not every form. Run
inside the dev backend container; the account it creates is @e2e and is
removed by `scripts.purge_e2e`.

    docker compose exec -T backend python - < docs/report/assets/phase-6/nul-byte-verdict/elsewhere.py
"""

import uuid

import httpx

API = "http://localhost:8000/api/v1"
http = httpx.Client(base_url=API, timeout=30)

email = f"nul-{uuid.uuid4().hex[:8]}@e2e.devpath.example"
probe = http.post(
    "/auth/register",
    json={"email": email, "password": "devpath-nul-drill", "full_name": "Thử\x00 NUL"},
)
print(f"POST /auth/register, full_name with a NUL (no sign-in needed) -> HTTP {probe.status_code}")

email = f"nul-{uuid.uuid4().hex[:8]}@e2e.devpath.example"
http.post(
    "/auth/register", json={"email": email, "password": "devpath-nul-drill", "full_name": "Thử NUL"}
).raise_for_status()
token = http.post("/auth/login", json={"email": email, "password": "devpath-nul-drill"}).json()[
    "access_token"
]
auth = {"Authorization": f"Bearer {token}"}
probe = http.patch("/users/me", json={"full_name": "Tên\x00"}, headers=auth)
print(f"PATCH /users/me, full_name with a NUL -> HTTP {probe.status_code}")
http.post("/auth/logout", headers=auth)
