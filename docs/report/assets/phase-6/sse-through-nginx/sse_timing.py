"""When does each server-sent event of one chat answer arrive?

    python sse_timing.py BASE_URL TOKEN SESSION_ID "question"

Standard library only, so the same file runs on the host (through nginx,
https://localhost) and inside the backend container (straight to uvicorn,
http://localhost:8000). Prints one JSON object: status, the headers that
decide buffering, and [ms since request, event, characters] per event, with
the time each event was *read off the socket* -- which is what a browser's
fetch reader sees.
"""

import http.client
import json
import ssl
import sys
import time
import urllib.parse

base, token, session_id, question = sys.argv[1:5]
url = urllib.parse.urlsplit(base)
if url.scheme == "https":
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE  # the prodtest certificate is self-signed
    conn = http.client.HTTPSConnection(url.hostname, url.port or 443, context=context, timeout=180)
else:
    conn = http.client.HTTPConnection(url.hostname, url.port or 80, timeout=180)

started = time.perf_counter()
conn.request(
    "POST",
    f"/api/v1/chat-sessions/{session_id}/messages",
    body=json.dumps({"content": question}),
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    },
)
response = conn.getresponse()
headers_at = (time.perf_counter() - started) * 1000

events = []
buffer = b""
reads = 0
while True:
    chunk = response.read1(65536)
    if not chunk:
        break
    reads += 1
    at = round((time.perf_counter() - started) * 1000)
    buffer += chunk
    while b"\n\n" in buffer:
        frame, buffer = buffer.split(b"\n\n", 1)
        lines = frame.decode("utf-8").split("\n")
        name = next((line[7:] for line in lines if line.startswith("event: ")), "?")
        data = next((line[6:] for line in lines if line.startswith("data: ")), "{}")
        size = len(json.loads(data).get("text", "")) if name == "delta" else 0
        events.append([at, name, size])

print(
    json.dumps(
        {
            "status": response.status,
            "headers_ms": round(headers_at),
            "socket_reads": reads,
            "headers": {
                key: response.getheader(key)
                for key in ("Content-Type", "Transfer-Encoding", "Content-Encoding", "X-Accel-Buffering")
            },
            "events": events,
        }
    )
)
