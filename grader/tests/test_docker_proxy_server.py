"""The proxy's HTTP plumbing, against a fake daemon on TCP.

The policy decides what may pass; these tests are about whether what the
policy decided is what actually reaches the daemon. That means: a refused
request never arrives at all, a second request smuggled behind an allowed one
is not forwarded, a body cannot be framed two ways, and attach -- the one
hijacked, two-way stream -- passes the client's half-close on, which is how
the submission learns its input has ended.

No real daemon here (the live suite runs the runner through a real one), so
these run on any machine, Windows included.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from proxy import policy, server

ROOT = "/var/lib/devpath-grading"
NAME = "devpath-grading-ea88257d6a284d0688ae3dd9f8e256c7"
CONTAINER_ID = "351f3e700402a40625ed0142f0ed8a028f7490fa3df51a9e29b2cf9402e23474"
CREATE_BODY = (Path(__file__).parent / "fixtures" / "docker_create_body.json").read_bytes()

GRADING_RECORD = {
    "Name": f"/{NAME}",
    "Config": {"Labels": {"devpath.grading": "1"}},
    "Mounts": [{"Type": "bind", "Source": f"{ROOT}/devpath-grading-nk3hif1e/code"}],
}
POSTGRES_RECORD = {"Name": "/devpath-postgres-1", "Config": {"Labels": {}}, "Mounts": []}


class FakeDaemon:
    """Records every request it receives and answers like the daemon would,
    closely enough for the proxy: inspect from a table, 101 + echo for attach."""

    def __init__(self, records: dict[str, dict]) -> None:
        self.records = records
        self.requests: list[tuple[str, bytes]] = []

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        head = (await reader.readuntil(b"\r\n\r\n")).decode("latin-1")
        length = 0
        for line in head.split("\r\n")[1:]:
            if line.lower().startswith("content-length:"):
                length = int(line.split(":", 1)[1])
        body = await reader.readexactly(length) if length else b""
        self.requests.append((head, body))
        method, target, _ = head.split("\r\n")[0].split(" ")
        path = target.split("?")[0]

        if path.endswith("/attach"):
            writer.write(b"HTTP/1.1 101 UPGRADED\r\nConnection: Upgrade\r\nUpgrade: tcp\r\n\r\n")
            await writer.drain()
            stdin = await reader.read()  # until the proxy passes the half-close on
            writer.write(stdin.upper())
            await writer.drain()
            writer.close()
            return

        if path.endswith("/json"):
            key = path.split("/")[-2]
            record = self.records.get(key)
            status, payload = (200, record) if record else (404, {"message": "No such container"})
        elif path.endswith("/containers/create"):
            status, payload = 201, {"Id": CONTAINER_ID, "Warnings": []}
        elif path.endswith("/_ping"):
            status, payload = 200, None
        else:
            status, payload = 204, None
        data = (
            b"OK" if path.endswith("/_ping") else (json.dumps(payload).encode() if payload else b"")
        )
        head = f"HTTP/1.1 {status} X\r\nContent-Length: {len(data)}\r\nConnection: close\r\n\r\n"
        writer.write(head.encode() + data)
        await writer.drain()
        writer.close()

    def forwarded(self) -> list[str]:
        """Request lines that reached the daemon, inspect lookups excluded."""
        return [
            head.split("\r\n")[0]
            for head, _ in self.requests
            if not (head.startswith("GET /containers/") and "/json" in head.split("\r\n")[0])
        ]


async def _with_proxy(records: dict[str, dict], exchange):
    daemon = FakeDaemon(records)
    upstream_server = await asyncio.start_server(daemon.handle, "127.0.0.1", 0)
    port = upstream_server.sockets[0].getsockname()[1]
    proxy = server.Proxy(
        policy.Config(workspace_root=ROOT), server.Upstream(f"tcp://127.0.0.1:{port}")
    )
    proxy_server = await asyncio.start_server(
        proxy.handle, "127.0.0.1", 0, limit=server.MAX_HEAD_BYTES
    )
    proxy_port = proxy_server.sockets[0].getsockname()[1]
    try:
        result = await exchange(proxy_port)
    finally:
        proxy_server.close()
        upstream_server.close()
    return daemon, result


async def _send(port: int, raw: bytes) -> bytes:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(raw)
    await writer.drain()
    data = await asyncio.wait_for(reader.read(), timeout=10)
    writer.close()
    return data


def _exchange(raw: bytes, records: dict[str, dict] | None = None) -> tuple[FakeDaemon, bytes]:
    records = {NAME: GRADING_RECORD, CONTAINER_ID: GRADING_RECORD} if records is None else records
    return asyncio.run(_with_proxy(records, lambda port: _send(port, raw)))


def _request(method: str, target: str, body: bytes = b"", extra: str = "") -> bytes:
    length = f"Content-Length: {len(body)}\r\n" if body else ""
    return (
        f"{method} {target} HTTP/1.1\r\nHost: api.moby.localhost\r\n{extra}{length}\r\n".encode()
        + body
    )


def _status(response: bytes) -> int:
    return int(response.split(b" ", 2)[1])


# --- what reaches the daemon -------------------------------------------------------


def test_an_allowed_request_is_forwarded_and_answered() -> None:
    daemon, response = _exchange(_request("HEAD", "/_ping"))
    assert _status(response) == 200
    assert daemon.forwarded() == ["HEAD /_ping HTTP/1.1"]


def test_every_forwarded_request_asks_the_daemon_to_hang_up_after_it() -> None:
    daemon, _ = _exchange(_request("HEAD", "/_ping", extra="Connection: keep-alive\r\n"))
    head = daemon.requests[0][0]
    assert "Connection: close" in head
    assert "keep-alive" not in head


def test_the_create_body_reaches_the_daemon_byte_for_byte() -> None:
    target = f"/v1.55/containers/create?name={NAME}"
    daemon, response = _exchange(
        _request("POST", target, CREATE_BODY, "Content-Type: application/json\r\n")
    )
    assert _status(response) == 201
    assert daemon.requests[0][1] == CREATE_BODY


def test_a_refused_create_never_reaches_the_daemon() -> None:
    body = json.loads(CREATE_BODY)
    body["HostConfig"]["Privileged"] = True
    target = f"/v1.55/containers/create?name={NAME}"
    daemon, response = _exchange(_request("POST", target, json.dumps(body).encode()))
    assert _status(response) == 403
    assert b"Privileged not allowed" in response
    assert daemon.requests == []


def test_a_refused_route_never_reaches_the_daemon() -> None:
    daemon, response = _exchange(_request("POST", "/v1.55/containers/devpath-postgres-1/exec"))
    assert _status(response) == 403
    assert json.loads(response.split(b"\r\n\r\n", 1)[1])["message"].startswith(
        "devpath-docker-proxy:"
    )
    assert daemon.requests == []


# --- whose container ---------------------------------------------------------------------


def test_an_operation_on_a_grading_container_is_checked_then_forwarded() -> None:
    daemon, response = _exchange(_request("POST", f"/v1.55/containers/{CONTAINER_ID}/start"))
    assert _status(response) == 204
    assert daemon.requests[0][0].startswith(f"GET /containers/{CONTAINER_ID}/json")
    assert daemon.forwarded() == [f"POST /v1.55/containers/{CONTAINER_ID}/start HTTP/1.1"]


def test_a_container_without_the_grading_label_is_refused() -> None:
    impostor = "f" * 64
    daemon, response = _exchange(
        _request("POST", f"/containers/{impostor}/kill"), records={impostor: POSTGRES_RECORD}
    )
    assert _status(response) == 403
    assert daemon.forwarded() == []


def test_a_container_that_does_not_exist_is_a_404_from_the_proxy() -> None:
    daemon, response = _exchange(_request("DELETE", f"/containers/{NAME}?force=1"), records={})
    assert _status(response) == 404
    assert daemon.forwarded() == []


# --- framing: the body that was checked is the body that is read -------------------------


def test_a_chunked_body_is_refused() -> None:
    raw = (
        f"POST /containers/create?name={NAME} HTTP/1.1\r\nHost: x\r\n"
        "Transfer-Encoding: chunked\r\n\r\n0\r\n\r\n"
    ).encode()
    daemon, response = _exchange(raw)
    assert _status(response) == 400
    assert daemon.requests == []


def test_two_content_lengths_are_refused() -> None:
    raw = _request("POST", f"/containers/create?name={NAME}", CREATE_BODY, "Content-Length: 1\r\n")
    daemon, response = _exchange(raw)
    assert _status(response) == 400
    assert daemon.requests == []


def test_a_folded_header_is_refused() -> None:
    raw = b"HEAD /_ping HTTP/1.1\r\nHost: x\r\nX-A: 1\r\n continued\r\n\r\n"
    daemon, response = _exchange(raw)
    assert _status(response) == 400
    assert daemon.requests == []


def test_a_second_request_behind_an_allowed_one_is_not_forwarded() -> None:
    smuggled = _request("HEAD", "/_ping") + _request(
        "POST", "/v1.55/containers/devpath-postgres-1/kill"
    )
    daemon, _ = _exchange(smuggled)
    assert daemon.forwarded() == ["HEAD /_ping HTTP/1.1"]


def test_an_upgrade_is_only_passed_on_for_attach() -> None:
    daemon, _ = _exchange(
        _request("HEAD", "/_ping", extra="Connection: Upgrade\r\nUpgrade: tcp\r\n")
    )
    head = daemon.requests[0][0]
    assert "Upgrade: tcp" not in head
    assert "Connection: close" in head


def test_an_oversized_head_is_refused() -> None:
    raw = b"HEAD /_ping HTTP/1.1\r\nX-Pad: " + b"a" * (server.MAX_HEAD_BYTES + 10) + b"\r\n\r\n"
    daemon, response = _exchange(raw)
    assert response == b"" or _status(response) == 400
    assert daemon.requests == []


# --- attach: two ways, and the half-close ------------------------------------------------


def test_attach_carries_stdin_up_output_down_and_the_end_of_input() -> None:
    async def exchange(port: int) -> bytes:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(
            _request(
                "POST",
                f"/v1.55/containers/{CONTAINER_ID}/attach?stderr=1&stdin=1&stdout=1&stream=1",
                extra="Connection: Upgrade\r\nUpgrade: tcp\r\n",
            )
        )
        await writer.drain()
        head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=10)
        assert b"101" in head
        writer.write(b"21\nsecond line\n")
        await writer.drain()
        # What the runner does when the test input file is exhausted. If the
        # proxy did not pass this on, the fake daemon -- like a submission
        # calling input() -- would wait forever, and this would time out.
        writer.write_eof()
        output = await asyncio.wait_for(reader.read(), timeout=10)
        writer.close()
        return output

    daemon, output = asyncio.run(_with_proxy({CONTAINER_ID: GRADING_RECORD}, exchange))
    assert output == b"21\nSECOND LINE\n"
    assert "Upgrade: tcp" in daemon.requests[-1][0]


# --- the daemon is away ----------------------------------------------------------------


def test_an_unreachable_daemon_is_a_502_not_a_hang() -> None:
    async def exchange() -> bytes:
        proxy = server.Proxy(
            policy.Config(workspace_root=ROOT), server.Upstream("tcp://127.0.0.1:9")
        )
        proxy_server = await asyncio.start_server(proxy.handle, "127.0.0.1", 0)
        port = proxy_server.sockets[0].getsockname()[1]
        try:
            return await _send(port, _request("HEAD", "/_ping"))
        finally:
            proxy_server.close()

    assert _status(asyncio.run(exchange())) == 502
