"""A Docker API proxy that lets the grading worker do exactly what grading needs.

    python -m proxy.server        (env: see `main`)

Until 02/10/2026 the grading worker held /var/run/docker.sock itself, which
made it root on the host by a single request: `docker run -v /:/host
--privileged`. It is the one container that has to start containers, so it
cannot be denied the daemon -- but it can be put behind something that only
forwards what a grading run looks like. `policy.py` is that definition; this
module is the plumbing.

Why not an off-the-shelf socket proxy: the common ones filter by endpoint
(allow POST to /containers/*), and once `create` is allowed, so is a create
with `Privileged: true` and the host's root bind-mounted -- the very request
the proxy exists to stop. The danger is in the body of one endpoint, so the
body has to be read.

How it speaks HTTP, and why:

  * one request per connection. Every forwarded request carries
    `Connection: close`, so the daemon hangs up after answering and the next
    request -- which must be checked too -- arrives on a new connection. A
    proxy that kept connections alive would have to parse every following
    request in the stream or let them through unchecked.
  * no chunked bodies, no ambiguity. A request with Transfer-Encoding, a
    repeated or non-numeric Content-Length, or folded headers is refused: the
    body that was checked must be the body the daemon reads.
  * attach is the exception: its connection is hijacked into a raw stream,
    stdin up and output down. Both directions are piped, and when the client
    closes its sending side (the runner has written all of the test input),
    that half-close is passed on -- without it the submission would wait for
    more input forever and be charged a time limit.
  * container operations are checked against the daemon's own record of the
    container (its label), fetched on a separate connection before the
    request is forwarded.

Standard library only; listens on TCP inside a compose network that only the
grading worker shares.
"""

from __future__ import annotations

import asyncio
import http.client
import json
import logging
import os
import socket
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

from proxy import policy

log = logging.getLogger("devpath.docker-proxy")

MAX_HEAD_BYTES = 16 * 1024
HEAD_TIMEOUT_SECONDS = 10
CHUNK = 64 * 1024
HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-connection",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


class BadRequest(Exception):
    pass


@dataclass(frozen=True)
class Upstream:
    """Where the daemon is: `unix:///var/run/docker.sock` or `tcp://host:port`."""

    url: str

    async def open(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        parts = urlsplit(self.url)
        if parts.scheme == "unix":
            return await asyncio.open_unix_connection(parts.path)
        return await asyncio.open_connection(parts.hostname, parts.port)

    def inspect(self, container: str) -> Mapping | None:
        """GET /containers/<name>/json, blocking -- run in a thread. None if
        there is no such container. `container` has already matched the strict
        name pattern, so it is safe in a path."""
        conn = _UpstreamHTTP(self.url)
        try:
            conn.request("GET", f"/containers/{container}/json", headers={"Host": "docker"})
            response = conn.getresponse()
            data = response.read()
        finally:
            conn.close()
        if response.status == 404:
            return None
        if response.status != 200:
            raise RuntimeError(f"daemon answered {response.status} to inspect")
        return json.loads(data)


class _UpstreamHTTP(http.client.HTTPConnection):
    def __init__(self, url: str) -> None:
        parts = urlsplit(url)
        self._unix_path = parts.path if parts.scheme == "unix" else None
        super().__init__(parts.hostname or "localhost", parts.port, timeout=10)

    def connect(self) -> None:
        if self._unix_path is None:
            super().connect()
            return
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect(self._unix_path)
        self.sock = sock


@dataclass(frozen=True)
class Request:
    method: str
    target: str
    headers: list[tuple[str, str]]
    content_length: int

    def header(self, name: str) -> str | None:
        for key, value in self.headers:
            if key.lower() == name:
                return value
        return None


def parse_head(head: bytes) -> Request:
    try:
        text = head.decode("latin-1")
    except UnicodeDecodeError:  # pragma: no cover -- latin-1 decodes anything
        raise BadRequest("undecodable head") from None
    lines = text.split("\r\n")
    request_line, header_lines = lines[0], [line for line in lines[1:] if line]
    parts = request_line.split(" ")
    if len(parts) != 3 or parts[2] not in ("HTTP/1.1", "HTTP/1.0"):
        raise BadRequest("malformed request line")
    method, target, _ = parts
    if not method.isalpha() or not method.isupper() or not target.startswith("/"):
        raise BadRequest("malformed request line")

    headers: list[tuple[str, str]] = []
    for line in header_lines:
        if line[0] in " \t" or ":" not in line:
            raise BadRequest("folded or malformed header")
        name, _, value = line.partition(":")
        if not name or name != name.strip() or not all(33 <= ord(c) < 127 for c in name):
            raise BadRequest("malformed header name")
        headers.append((name, value.strip()))

    lengths = [v for k, v in headers if k.lower() == "content-length"]
    if any(k.lower() == "transfer-encoding" for k, _ in headers):
        raise BadRequest("chunked or encoded request bodies are not accepted")
    if len(lengths) > 1 or (lengths and not lengths[0].isdigit()):
        raise BadRequest("ambiguous Content-Length")
    length = int(lengths[0]) if lengths else 0
    if length > policy.MAX_BODY_BYTES:
        raise BadRequest("request body too large")
    return Request(method=method, target=target, headers=headers, content_length=length)


def rebuild_head(request: Request, *, upgrade: bool) -> bytes:
    """The request as forwarded: the client's end-to-end headers, and our own
    Connection header -- `close` everywhere except a hijacked attach."""
    lines = [f"{request.method} {request.target} HTTP/1.1"]
    lines += [f"{k}: {v}" for k, v in request.headers if k.lower() not in HOP_BY_HOP]
    if upgrade:
        lines += ["Connection: Upgrade", "Upgrade: tcp"]
    else:
        lines.append("Connection: close")
    return ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1")


def _response(status: int, reason: str, message: str) -> bytes:
    body = json.dumps({"message": f"devpath-docker-proxy: {message}"}).encode()
    return (
        f"HTTP/1.1 {status} {reason}\r\nContent-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n"
    ).encode() + body


async def _pipe(source: asyncio.StreamReader, sink: asyncio.StreamWriter) -> None:
    try:
        while data := await source.read(CHUNK):
            sink.write(data)
            await sink.drain()
    except (ConnectionError, asyncio.IncompleteReadError):
        pass
    finally:
        # Pass the end of this direction on, and only this direction.
        if sink.can_write_eof() and not sink.is_closing():
            try:
                sink.write_eof()
            except (OSError, RuntimeError):
                pass


class Proxy:
    def __init__(self, config: policy.Config, upstream: Upstream) -> None:
        self.config = config
        self.upstream = upstream

    async def handle(self, client_r: asyncio.StreamReader, client_w: asyncio.StreamWriter) -> None:
        summary = "?"
        try:
            try:
                head = await asyncio.wait_for(
                    client_r.readuntil(b"\r\n\r\n"), timeout=HEAD_TIMEOUT_SECONDS
                )
            except asyncio.LimitOverrunError:
                raise BadRequest("request head too large") from None
            except (asyncio.IncompleteReadError, TimeoutError):
                return
            request = parse_head(head)
            summary = f"{request.method} {urlsplit(request.target).path}"
            body = (
                await client_r.readexactly(request.content_length)
                if request.content_length
                else b""
            )

            route = policy.route(request.method, request.target)
            if route.kind is policy.Kind.CREATE:
                policy.check_create(route, body, self.config)
            elif body:
                raise policy.Denied(f"{route.kind} takes no body")
            if route.container is not None:
                inspected = await asyncio.to_thread(self.upstream.inspect, route.container)
                if inspected is None:
                    client_w.write(
                        _response(404, "Not Found", f"No such container: {route.container}")
                    )
                    log.info("%s -> 404 (no such container)", summary)
                    return
                policy.check_owned(inspected, route.kind, self.config)

            log.info("%s -> allowed", summary)
            await self._forward(request, body, route, client_r, client_w)
        except policy.Denied as denied:
            log.warning("%s -> DENIED: %s", summary, denied)
            client_w.write(_response(403, "Forbidden", str(denied)))
        except BadRequest as bad:
            log.warning("%s -> BAD REQUEST: %s", summary, bad)
            client_w.write(_response(400, "Bad Request", str(bad)))
        except (OSError, RuntimeError) as exc:
            log.error("%s -> daemon unreachable: %s", summary, exc)
            client_w.write(_response(502, "Bad Gateway", "the Docker daemon did not answer"))
        finally:
            try:
                await client_w.drain()
            except (ConnectionError, RuntimeError):
                pass
            client_w.close()

    async def _forward(
        self,
        request: Request,
        body: bytes,
        route: policy.Route,
        client_r: asyncio.StreamReader,
        client_w: asyncio.StreamWriter,
    ) -> None:
        up_r, up_w = await self.upstream.open()
        try:
            upgrade = route.streams_both_ways and (request.header("upgrade") or "").lower() == "tcp"
            up_w.write(rebuild_head(request, upgrade=upgrade) + body)
            await up_w.drain()
            if route.streams_both_ways:
                # stdin up, output down; the response ends when the daemon
                # closes, which is when the container's streams close.
                upward = asyncio.create_task(_pipe(client_r, up_w))
                await _pipe(up_r, client_w)
                upward.cancel()
            else:
                await _pipe(up_r, client_w)
        finally:
            up_w.close()


def _listen_address(value: str) -> tuple[str, int]:
    host, _, port = value.rpartition(":")
    return host or "0.0.0.0", int(port)


async def serve(config: policy.Config, upstream: Upstream, listen: str) -> None:
    proxy = Proxy(config, upstream)
    host, port = _listen_address(listen)
    server = await asyncio.start_server(proxy.handle, host, port, limit=MAX_HEAD_BYTES)
    log.info(
        "listening on %s:%d -> %s; images %s; workspace %s",
        host,
        port,
        upstream.url,
        ",".join(sorted(config.images)),
        config.workspace_root,
    )
    async with server:
        await server.serve_forever()


def health(listen: str) -> int:
    """The container healthcheck: a ping through the proxy itself, so green
    means both the proxy and the daemon behind it are answering."""
    host, port = _listen_address(listen)
    host = "127.0.0.1" if host in ("", "0.0.0.0") else host
    try:
        with socket.create_connection((host, port), timeout=5) as conn:
            conn.sendall(b"HEAD /_ping HTTP/1.1\r\nHost: health\r\n\r\n")
            return 0 if conn.recv(64).startswith(b"HTTP/1.1 200") else 1
    except OSError:
        return 1


def main() -> None:
    listen = os.environ.get("DOCKER_PROXY_LISTEN", "0.0.0.0:2375")
    if sys.argv[1:] == ["health"]:
        sys.exit(health(listen))
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout
    )
    config = policy.Config.from_env(os.environ)
    upstream = Upstream(os.environ.get("DOCKER_PROXY_UPSTREAM", "unix:///var/run/docker.sock"))
    asyncio.run(serve(config, upstream, listen))


if __name__ == "__main__":
    main()
