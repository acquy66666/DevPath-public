"""A NUL character in what a client sends: which requests become a 500?

Over real HTTP, against a running API (uvicorn) on the dev database. Run it
inside the container that serves the code being measured:

    docker exec -i <container> python - < docs/report/assets/phase-6/nul-everywhere/drill.py

Every account it creates is @e2e.devpath.example: `python -m scripts.purge_e2e`
removes them (and their enrollment, cart and chat session) afterwards.

One probe asks the course assistant a question, so it spends one embedding
call and possibly one answer from Gemini when the API lets it through.
"""

import json
import os
import socket
import uuid

import httpx

API = os.environ.get("DRILL_API", "http://localhost:8000/api/v1")
HOST, PORT = "localhost", 8000
PASSWORD = "devpath-nul-drill"
FREE_COURSE = "python-co-ban-cho-nguoi-moi-bat-dau"

http = httpx.Client(base_url=API, timeout=60)


def show(label: str, response: httpx.Response) -> httpx.Response:
    code = ""
    try:
        detail = response.json().get("detail")
        if isinstance(detail, dict):
            code = detail.get("code", "")
            errors = detail.get("errors") or []
            if errors:
                code += f" {errors[0].get('type')} @ {'.'.join(map(str, errors[0].get('loc', [])))}"
    except (ValueError, AttributeError):
        pass
    print(f"  {label:<62} -> HTTP {response.status_code} {code}".rstrip())
    return response


def register(full_name: str) -> tuple[str, httpx.Response]:
    email = f"nul-{uuid.uuid4().hex[:8]}@e2e.devpath.example"
    response = http.post(
        "/auth/register", json={"email": email, "password": PASSWORD, "full_name": full_name}
    )
    return email, response


def sign_in(email: str) -> dict[str, str]:
    token = http.post("/auth/login", json={"email": email, "password": PASSWORD}).json()[
        "access_token"
    ]
    return {"Authorization": f"Bearer {token}"}


print("1. Without signing in")
email, response = register("Thử\x00 NUL")
show("POST /auth/register, full_name has a NUL", response)
probe = http.post("/auth/login", json={"email": email, "password": PASSWORD})
print(f"     ... and that account exists afterwards: {probe.status_code == 200}")
show(
    "POST /auth/login, email has a NUL",
    http.post("/auth/login", json={"email": "ai\x00@e2e.devpath.example", "password": PASSWORD}),
)
show("GET /courses?q=py<NUL>thon  (query string)", http.get("/courses", params={"q": "py\x00thon"}))
show("GET /courses/by-slug/py%00thon  (path)", http.get("/courses/by-slug/py%00thon"))
show("GET /certificates/ABCD%00EFGH  (path)", http.get("/certificates/ABCD%00EFGH"))
show(
    "GET /payments/vnpay/ipn?vnp_TxnRef=<NUL>  (logged to jsonb)",
    http.get("/payments/vnpay/ipn", params={"vnp_TxnRef": "DP\x00", "vnp_Amount": "100"}),
)

print("\n2. Signed in as a fresh student")
email, response = register("Học Viên NUL")
response.raise_for_status()
auth = sign_in(email)
show("PATCH /users/me, full_name has a NUL", http.patch(
    "/users/me", json={"full_name": "Tên\x00"}, headers=auth
))
name = http.get("/auth/me", headers=auth).json()["full_name"]
print(f"     ... full_name afterwards: {name!r}")

catalogue = {c["slug"]: c for c in http.get("/courses", params={"page_size": 50}).json()["items"]}
paid = next(c for c in catalogue.values() if float(c["price"]) > 0)
http.put(f"/cart/courses/{paid['id']}", headers=auth).raise_for_status()
show("POST /cart/coupon, code has a NUL", http.post(
    "/cart/coupon", json={"code": "GIAM\x00"}, headers=auth
))
show("POST /reports, details has a NUL", http.post(
    "/reports",
    json={"target_type": "course", "target_id": paid["id"], "reason": "other", "details": "x\x00"},
    headers=auth,
))

free = catalogue[FREE_COURSE]
http.post(f"/courses/{free['id']}/enroll", headers=auth).raise_for_status()
chat = http.post(f"/courses/{free['id']}/chat-sessions", headers=auth)
chat.raise_for_status()
events: list[str] = []
with http.stream(
    "POST",
    f"/chat-sessions/{chat.json()['id']}/messages",
    json={"content": "Vòng lặp for là gì?\x00"},
    headers=auth,
) as stream:
    body = stream.read()
    if stream.headers.get("content-type", "").startswith("text/event-stream"):
        for line in body.decode().splitlines():
            if line.startswith("event:"):
                name = line.split(":", 1)[1].strip()
                if not events or events[-1] != name:
                    events.append(name)
        error = next(
            (json.loads(line[5:]) for line in body.decode().splitlines() if '"code"' in line),
            None,
        )
        print(
            f"  {'POST /chat-sessions/{id}/messages, question has a NUL':<62} -> HTTP "
            f"{stream.status_code} stream: {' > '.join(events)}"
            + (f" ({error.get('code')})" if error else "")
        )
    else:
        show("POST /chat-sessions/{id}/messages, question has a NUL", stream)
stored = http.get(f"/chat-sessions/{chat.json()['id']}/messages", headers=auth).json()["total"]
print(f"     ... messages stored in that session: {stored}")

print("\n3. Controls")
email, response = register("Gạch chéo \\u0000 thật")
show('POST /auth/register, full_name "\\u0000" as six characters', response)
if response.status_code == 201:
    name = http.get("/auth/me", headers=sign_in(email)).json()["full_name"]
    print(f"     ... stored as {name!r}, NUL inside: {chr(0) in name}")
raw = json.dumps(
    {"email": f"raw-{uuid.uuid4().hex[:6]}@e2e.devpath.example", "password": PASSWORD,
     "full_name": "AB"}
).replace("AB", "A\x00B").encode()
show("POST /auth/register, raw 0x00 byte inside the JSON text", http.post(
    "/auth/register", content=raw, headers={"Content-Type": "application/json"}
))
with socket.create_connection((HOST, PORT), timeout=10) as conn:
    conn.sendall(b"GET /api/v1/health HTTP/1.1\r\nHost: x\r\nX-Probe: a\x00b\r\n\r\n")
    status_line = conn.recv(200).split(b"\r\n", 1)[0].decode()
print(f"  {'GET /health, header value has a 0x00 byte (raw socket)':<62} -> {status_line}")
