#!/usr/bin/env python3
"""Watches the production stack from the host, once a minute, and says so when
something breaks -- and again when it is fixed.

Runs on the VPS itself, from a systemd timer (devpath-monitor.timer), not in a
container. Reading every container's health means talking to the Docker
daemon, and on this host exactly one container holds the socket: the Docker
proxy (grader/proxy), which lets the grading worker do grading and nothing
else -- listing containers is not grading. The host already has the daemon
and the restart policy; the monitor sits next to them.

    check        one round: look, decide, notify (what the timer runs)
    status       what the last round found, for a human on the server
    test-alert   send a notification now, to prove the phone gets it

What one round looks at:

    service:<name>   every service compose says should be running is, and its
                     own healthcheck says healthy; one that restarted since the
                     last round is reported once, even if it came back
    site, api,       https://DOMAIN/, /api/v1/health and the course catalogue
    catalog          answer through nginx, asked on 127.0.0.1:443 with the real
                     name, so TLS and the routing are in the path -- and the
                     catalogue, unlike /health, needs the database
    tls              the certificate nginx is serving right now verifies and
                     has at least MONITOR_CERT_MIN_DAYS left
    disk             the disk holding Docker's data keeps MONITOR_DISK_MIN_FREE_PERCENT

A problem is announced once it has been seen on MONITOR_CONFIRM_RUNS rounds in
a row (a container being replaced by a deploy is not an incident), repeated
every REMIND_EVERY while it lasts, and closed with a "recovered" message.
Notifications go to ntfy (MONITOR_NTFY_URL); one that cannot be delivered waits
in an outbox for the next round. Without a URL, rounds still run and log.

What it does not see is this machine disappearing: nothing on a dead host can
report that. That is the external uptime check's job (docs/huong-dan-deploy-vps.md).

Standard library only, so the host needs nothing but the python3 Ubuntu ships.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

#: Vietnam does not observe daylight saving, so a fixed offset is the zone --
#: the same choice as the backend's `app/core/clock.py`.
VIETNAM = timezone(timedelta(hours=7))

INFRA = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE = INFRA / ".env.prod"
DEFAULT_COMPOSE_FILE = INFRA / "docker-compose.prod.yml"
DEFAULT_PROJECT = "devpath"
DEFAULT_STATE_DIR = Path("/var/lib/devpath-monitor")

#: Restart policies that mean "this should be running all the time". Anything
#: else -- `no`, `on-failure` -- is a job that runs and exits.
LONG_RUNNING = {"always", "unless-stopped"}

#: certbot renews at 30 days left and nginx reloads every 6 hours, so a served
#: certificate never has fewer than ~29 days. Under 14 means one of the two
#: stopped, with two weeks left to notice.
DEFAULT_CERT_MIN_DAYS = 14
DEFAULT_DISK_MIN_FREE_PERCENT = 10
#: Two rounds a minute apart: long enough for a deploy's container swap, short
#: enough that a real outage is announced inside two minutes.
DEFAULT_CONFIRM_RUNS = 2
REMIND_EVERY = timedelta(hours=6)
OUTBOX_LIMIT = 20

HTTP_TIMEOUT = 10
DOCKER_TIMEOUT = 30

#: ntfy priorities: 5 rings through Do Not Disturb on most phones -- kept for
#: the site being unreachable, which is the one a student would see.
URGENT, HIGH, DEFAULT = 5, 4, 3

LOGS_HINT = (
    "Xem log: docker compose -f docker-compose.prod.yml --env-file .env.prod"
    " logs --tail 100 <service>"
)


class ConfigError(Exception):
    """The env file is missing or does not say what the monitor needs."""


# --- configuration -------------------------------------------------------------


def read_env_file(path: Path) -> dict[str, str]:
    """`KEY=VALUE` lines, the subset of compose's env-file format this project
    writes: comments, blank lines, optional matching quotes. Only what the
    monitor asks for is used -- the file also holds the database password, and
    that stays out of this process's environment."""
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        values[key.strip()] = value
    return values


@dataclass(frozen=True)
class Config:
    domain: str
    project: str = DEFAULT_PROJECT
    compose_file: Path = DEFAULT_COMPOSE_FILE
    env_file: Path = DEFAULT_ENV_FILE
    state_dir: Path = DEFAULT_STATE_DIR
    https_address: tuple[str, int] = ("127.0.0.1", 443)
    tls_ca_file: str | None = None
    cert_min_days: int = DEFAULT_CERT_MIN_DAYS
    disk_path: str = "/var/lib/docker"
    disk_min_free_percent: float = DEFAULT_DISK_MIN_FREE_PERCENT
    confirm_runs: int = DEFAULT_CONFIRM_RUNS
    ntfy_url: str = ""
    heartbeat_url: str = ""


def _int(env: Mapping[str, str], name: str, default: int, minimum: int) -> int:
    raw = env.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name}={raw!r} is not a whole number") from None
    if value < minimum:
        raise ConfigError(f"{name} must be at least {minimum}")
    return value


def _address(raw: str) -> tuple[str, int]:
    host, sep, port = raw.rpartition(":")
    if not sep or not host or not port.isdigit():
        raise ConfigError(f"MONITOR_HTTPS_ADDRESS={raw!r} is not host:port")
    return host.strip("[]"), int(port)


def config_from(
    file_env: Mapping[str, str],
    process_env: Mapping[str, str],
    *,
    env_file: Path,
    compose_file: Path,
    state_dir: Path,
    project: str,
) -> Config:
    """The env file says what production is; the process environment may
    override any of it, which is how a test stack on a dev machine points the
    same script somewhere else."""
    env = {**file_env, **{k: v for k, v in process_env.items() if k.startswith("MONITOR_")}}
    if "DOMAIN" in process_env:
        env["DOMAIN"] = process_env["DOMAIN"]

    domain = env.get("DOMAIN", "").strip()
    if not domain:
        raise ConfigError(f"DOMAIN is not set in {env_file}")

    ntfy_url = env.get("MONITOR_NTFY_URL", "").strip()
    if ntfy_url:
        ntfy_endpoint(ntfy_url)  # refuse a malformed URL now, not at 3 a.m.

    return Config(
        domain=domain,
        project=project,
        compose_file=compose_file,
        env_file=env_file,
        state_dir=state_dir,
        https_address=_address(env.get("MONITOR_HTTPS_ADDRESS", "").strip() or "127.0.0.1:443"),
        tls_ca_file=env.get("MONITOR_TLS_CA", "").strip() or None,
        cert_min_days=_int(env, "MONITOR_CERT_MIN_DAYS", DEFAULT_CERT_MIN_DAYS, 1),
        disk_path=env.get("MONITOR_DISK_PATH", "").strip() or "/var/lib/docker",
        disk_min_free_percent=_int(
            env, "MONITOR_DISK_MIN_FREE_PERCENT", DEFAULT_DISK_MIN_FREE_PERCENT, 0
        ),
        confirm_runs=_int(env, "MONITOR_CONFIRM_RUNS", DEFAULT_CONFIRM_RUNS, 1),
        ntfy_url=ntfy_url,
        heartbeat_url=env.get("MONITOR_HEARTBEAT_URL", "").strip(),
    )


# --- what the containers say ---------------------------------------------------


@dataclass(frozen=True)
class Container:
    id: str
    service: str
    status: str  # running, restarting, exited, paused, dead, created
    health: str  # healthy, unhealthy, starting, or "" without a healthcheck
    exit_code: int
    oom_killed: bool
    restart_count: int


#: One line per container, fields chosen by name. The full `docker inspect`
#: carries every container's environment -- the database password among it --
#: and none of that needs to pass through here.
#:
#: `index .State "Health"`, not `.State.Health`: the template sees State as a
#: map, and a container with no healthcheck (beat, certbot) has no such key --
#: the plain form fails the whole command, for every container. Found by the
#: drill, on its first round.
INSPECT_FORMAT = (
    '{{.Id}}\t{{index .Config.Labels "com.docker.compose.service"}}'
    '\t{{index .Config.Labels "com.docker.compose.oneoff"}}\t{{.RestartCount}}'
    '\t{{.State.Status}}\t{{with index .State "Health"}}{{.Status}}{{end}}'
    "\t{{.State.ExitCode}}\t{{.State.OOMKilled}}"
)


def parse_inspect(output: str) -> list[Container]:
    """`docker inspect --format INSPECT_FORMAT` -> containers, leaving out the
    one-off ones (`compose run --rm`: a migration, a restore) that come and go
    on purpose."""
    containers = []
    for line in output.splitlines():
        if not line.strip():
            continue
        cid, service, oneoff, restarts, status, health, exit_code, oom = line.split("\t")
        if oneoff == "True" or not service:
            continue
        containers.append(
            Container(
                id=cid,
                service=service,
                status=status,
                health=health,
                exit_code=int(exit_code),
                oom_killed=oom == "true",
                restart_count=int(restarts),
            )
        )
    return containers


def expected_services(compose_config: Mapping) -> dict[str, bool]:
    """Service name -> whether it should always be running, from
    `docker compose config --format json`. The compose file is the list, so a
    service added there is watched without touching this script."""
    services = compose_config.get("services", {})
    return {name: spec.get("restart", "no") in LONG_RUNNING for name, spec in services.items()}


def _exit_detail(c: Container) -> str:
    detail = f"mã thoát {c.exit_code}"
    if c.oom_killed:
        detail += ", hết bộ nhớ (OOM)"
    return detail


def service_findings(
    expected: Mapping[str, bool], containers: Iterable[Container]
) -> dict[str, str]:
    by_service: dict[str, list[Container]] = {}
    for c in containers:
        by_service.setdefault(c.service, []).append(c)

    findings = {}
    for service, long_running in sorted(expected.items()):
        mine = by_service.get(service, [])
        key = f"service:{service}"

        if not long_running:
            # A job: fine absent, fine having exited 0, wrong having failed.
            failed = [c for c in mine if c.status == "exited" and c.exit_code != 0]
            if failed and not any(c.status == "running" for c in mine):
                findings[key] = f"tác vụ một lần bị lỗi ({_exit_detail(failed[0])})"
            continue

        if not mine:
            findings[key] = "không có container"
            continue
        running = [c for c in mine if c.status == "running"]
        if not running:
            c = mine[0]
            if c.status == "restarting":
                findings[key] = f"khởi động lại liên tục ({_exit_detail(c)})"
            elif c.status == "exited":
                findings[key] = f"đã dừng ({_exit_detail(c)})"
            else:
                findings[key] = f"không chạy ({c.status})"
            continue
        # `starting` is a container inside its start period; Docker turns it
        # into `unhealthy` by itself if it never gets there.
        if any(c.health == "unhealthy" for c in running):
            findings[key] = "healthcheck báo unhealthy"
    return findings


def restart_events(
    previous: Mapping[str, int], containers: Iterable[Container]
) -> tuple[list[str], dict[str, int]]:
    """Containers Docker restarted since the last round -- a crash it already
    recovered from, which no other check would ever show. Counted per
    container id: a container recreated by a deploy starts again from zero and
    is not a restart."""
    events, counts = [], {}
    for c in containers:
        counts[c.id] = c.restart_count
        before = previous.get(c.id)
        if before is not None and c.restart_count > before:
            times = c.restart_count - before
            line = f"{c.service}: Docker tự khởi động lại {times} lần"
            if c.oom_killed:
                line += " (lần gần nhất vì hết bộ nhớ)"
            events.append(line)
    return events, counts


def _docker(args: list[str]) -> str:
    result = subprocess.run(
        ["docker", *args],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=DOCKER_TIMEOUT,
        check=False,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip().splitlines()
        raise RuntimeError(message[-1] if message else f"docker exited {result.returncode}")
    return result.stdout


def read_containers(config: Config) -> tuple[dict[str, bool], list[Container]]:
    # Uninterpolated: restart policies are literal in the file, and this way
    # the rendered config carries `${POSTGRES_PASSWORD}` rather than its value.
    compose_config = _docker(
        [
            "compose",
            "-p",
            config.project,
            "-f",
            str(config.compose_file),
            "config",
            "--no-interpolate",
            "--format",
            "json",
        ]
    )
    expected = expected_services(json.loads(compose_config))
    ids = _docker(
        [
            "ps",
            "-a",
            "-q",
            "--no-trunc",
            "--filter",
            f"label=com.docker.compose.project={config.project}",
        ]
    ).split()
    if not ids:
        return expected, []
    return expected, parse_inspect(_docker(["inspect", "--format", INSPECT_FORMAT, *ids]))


# --- what nginx answers ----------------------------------------------------------


class _PinnedHTTPS(http.client.HTTPSConnection):
    """An HTTPS request for `domain` sent to one fixed address. The name still
    goes in SNI and the Host header, so nginx picks the real vhost and the real
    certificate -- only DNS is skipped, which is not what is being tested."""

    def __init__(self, domain: str, address: tuple[str, int], context: ssl.SSLContext) -> None:
        super().__init__(domain, address[1], timeout=HTTP_TIMEOUT, context=context)
        self._address = address
        self._tls = context

    def connect(self) -> None:
        sock = socket.create_connection(self._address, self.timeout)
        self.sock = self._tls.wrap_socket(sock, server_hostname=self.host)


def _contexts(ca_file: str | None) -> tuple[ssl.SSLContext, ssl.SSLContext]:
    verified = ssl.create_default_context(cafile=ca_file)
    unverified = ssl.create_default_context()
    unverified.check_hostname = False
    unverified.verify_mode = ssl.CERT_NONE
    return verified, unverified


def tls_finding(config: Config, now: datetime) -> tuple[str | None, bool]:
    """(problem with the served certificate or None, whether it verified).
    A connection that fails outright is not a certificate problem -- the site
    and API checks report that -- so it comes back as (None, False)."""
    verified, _ = _contexts(config.tls_ca_file)
    try:
        with (
            socket.create_connection(config.https_address, HTTP_TIMEOUT) as raw,
            verified.wrap_socket(raw, server_hostname=config.domain) as tls,
        ):
            cert = tls.getpeercert()
    except ssl.SSLCertVerificationError as exc:
        return f"không hợp lệ: {exc.verify_message}", False
    except (OSError, ssl.SSLError):
        return None, False

    expires = datetime.fromtimestamp(ssl.cert_time_to_seconds(cert["notAfter"]), UTC)
    left = expires - now
    if left < timedelta(days=config.cert_min_days):
        when = expires.astimezone(VIETNAM).strftime("%d/%m/%Y")
        return f"còn {max(left.days, 0)} ngày là hết hạn ({when})", True
    return None, True


def http_status(config: Config, path: str, *, verify: bool) -> tuple[int | None, str]:
    """(status, "") or (None, why it could not be asked)."""
    verified, unverified = _contexts(config.tls_ca_file)
    conn = _PinnedHTTPS(config.domain, config.https_address, verified if verify else unverified)
    try:
        conn.request("GET", path, headers={"User-Agent": "devpath-monitor"})
        response = conn.getresponse()
        response.read(65536)
        return response.status, ""
    except (OSError, http.client.HTTPException) as exc:
        return None, str(exc) or type(exc).__name__
    finally:
        conn.close()


def http_findings(config: Config, *, verify: bool) -> dict[str, str]:
    findings = {}
    # /api/v1/health needs nginx and the API process, and on purpose nothing
    # more. The catalogue needs the database too: with Postgres stopped, the
    # drill found the home page still 200 (Next renders an empty state) and
    # /health still 200 -- only this one answered 500, which is what a visitor
    # browsing courses would get.
    for key, path, ok in (
        ("site", "/", lambda s: 200 <= s < 400),
        ("api", "/api/v1/health", lambda s: s == 200),
        ("catalog", "/api/v1/courses?page_size=1", lambda s: s == 200),
    ):
        status, error = http_status(config, path, verify=verify)
        if status is None:
            findings[key] = f"không kết nối được ({error})"
        elif not ok(status):
            findings[key] = f"trả HTTP {status}"
    return findings


def disk_finding(path: str, min_free_percent: float) -> tuple[str | None, str]:
    """(problem or None, a one-line reading for the log)."""
    target = path if os.path.exists(path) else os.path.abspath(os.sep)
    usage = shutil.disk_usage(target)
    free_percent = usage.free / usage.total * 100
    reading = f"đĩa trống {free_percent:.0f}% ({usage.free / 2**30:.1f} GB) ở {target}"
    if free_percent < min_free_percent:
        return f"{reading}, dưới ngưỡng {min_free_percent:g}%", reading
    return None, reading


# --- deciding what to say --------------------------------------------------------


@dataclass
class Problem:
    detail: str
    first_seen: str  # ISO 8601, UTC
    runs: int
    alerted_at: str | None = None


@dataclass
class State:
    checked_at: str | None = None
    problems: dict[str, Problem] = field(default_factory=dict)
    restarts: dict[str, int] = field(default_factory=dict)
    outbox: list[dict] = field(default_factory=list)

    @classmethod
    def from_json(cls, data: Mapping) -> State:
        return cls(
            checked_at=data.get("checked_at"),
            problems={k: Problem(**v) for k, v in data.get("problems", {}).items()},
            restarts={k: int(v) for k, v in data.get("restarts", {}).items()},
            outbox=list(data.get("outbox", [])),
        )

    def to_json(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Message:
    title: str
    body: str
    priority: int
    tags: tuple[str, ...]

    def to_json(self) -> dict:
        return {
            "title": self.title,
            "body": self.body,
            "priority": self.priority,
            "tags": list(self.tags),
        }


LABELS = {
    "site": "Trang chủ",
    "api": "API /api/v1/health",
    "catalog": "Danh mục khóa học (API + CSDL)",
    "tls": "Chứng chỉ TLS",
    "disk": "Ổ đĩa",
    "docker": "Docker",
}


def label(key: str) -> str:
    if key.startswith("service:"):
        return f"Service {key.removeprefix('service:')}"
    return LABELS.get(key, key)


def _parse(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp)


def _clock(moment: datetime) -> str:
    return moment.astimezone(VIETNAM).strftime("%H:%M %d/%m")


def _duration(span: timedelta) -> str:
    minutes = max(int(span.total_seconds() // 60), 1)
    if minutes < 60:
        return f"{minutes} phút"
    hours, minutes = divmod(minutes, 60)
    if hours < 48:
        return f"{hours} giờ {minutes} phút" if minutes else f"{hours} giờ"
    return f"{hours // 24} ngày {hours % 24} giờ"


def _grouped(items: list[tuple[str, str]]) -> list[str]:
    """`[(what, how)]` -> one line per distinct `how`. nginx being down fails
    the home page, the API and the catalogue with the same connection error,
    and a phone screen should say that once."""
    by_text: dict[str, list[str]] = {}
    for what, how in items:
        by_text.setdefault(how, []).append(what)
    return [f"{', '.join(whats)}: {how}" for how, whats in by_text.items()]


def evaluate(
    previous: State,
    findings: Mapping[str, str],
    events: list[str],
    now: datetime,
    *,
    confirm_runs: int,
    domain: str,
    remind_every: timedelta = REMIND_EVERY,
) -> tuple[State, Message | None]:
    """The whole policy, with no I/O: this round's findings against the last
    round's state -> the next state, and the one message to send, if any.

    The outbox and restart counts are carried by the caller; this decides
    which problems are new, confirmed, still going or over."""
    stamp = now.isoformat()
    problems: dict[str, Problem] = {}
    fresh, ongoing, recovered = [], [], []

    for key, detail in sorted(findings.items()):
        old = previous.problems.get(key)
        problem = Problem(
            detail=detail,
            first_seen=old.first_seen if old else stamp,
            runs=(old.runs if old else 0) + 1,
            alerted_at=old.alerted_at if old else None,
        )
        since = _clock(_parse(problem.first_seen))
        if problem.runs >= confirm_runs:
            if problem.alerted_at is None:
                fresh.append((label(key), f"{detail} (từ {since})"))
                problem.alerted_at = stamp
            elif now - _parse(problem.alerted_at) >= remind_every:
                ongoing.append((label(key), f"{detail} (từ {since})"))
                problem.alerted_at = stamp
        problems[key] = problem

    for key, old in sorted(previous.problems.items()):
        # Never announced -> never closed: a blip shorter than the confirmation
        # window stays out of the phone in both directions.
        if key not in findings and old.alerted_at is not None:
            recovered.append((label(key), f"ổn lại sau {_duration(now - _parse(old.first_seen))}"))

    state = State(checked_at=stamp, problems=problems)
    if not (fresh or ongoing or recovered or events):
        return state, None

    lines: list[str] = []
    if fresh:
        title = f"DevPath: {len(fresh)} sự cố mới"
        site_down = any(
            k in findings and problems[k].alerted_at == stamp for k in ("site", "api", "catalog")
        )
        priority, tags = (URGENT if site_down else HIGH), ("rotating_light",)
    elif ongoing:
        title = f"DevPath: vẫn còn {len(ongoing)} sự cố"
        priority, tags = HIGH, ("warning",)
    elif recovered:
        title = "DevPath: đã ổn lại"
        priority, tags = DEFAULT, ("white_check_mark",)
    else:
        title = "DevPath: service tự khởi động lại"
        priority, tags = DEFAULT, ("arrows_counterclockwise",)

    lines += [f"✗ {line}" for line in _grouped(fresh + ongoing)]
    lines += [f"✓ {line}" for line in _grouped(recovered)]
    lines += [f"↻ {e}" for e in events]

    # Announced on an earlier round and not repeated in this one: a "recovered"
    # message must not read as "everything is fine" while they last.
    still_down = [
        label(k) for k, p in problems.items() if p.alerted_at is not None and p.alerted_at != stamp
    ]
    if still_down:
        lines.append("Vẫn đang lỗi: " + ", ".join(still_down))
    if fresh or ongoing or events:
        lines.append(LOGS_HINT)
    lines.append(f"{domain} · {_clock(now)}")
    return state, Message(title=title, body="\n".join(lines), priority=priority, tags=tags)


def summary(findings: Mapping[str, str], readings: Iterable[str]) -> str:
    """The one line each round leaves in the journal."""
    if findings:
        problems = "; ".join(f"{label(k)}: {v}" for k, v in sorted(findings.items()))
        return f"{len(findings)} vấn đề — {problems}"
    return "ổn — " + ", ".join(readings)


# --- telling someone ---------------------------------------------------------------


def ntfy_endpoint(url: str) -> tuple[str, str]:
    """`https://ntfy.sh/<topic>` -> (where to POST, topic). Published as JSON
    to the server root rather than as a plain POST with headers: a title in
    Vietnamese is not something an HTTP header can carry."""
    parsed = urllib.parse.urlsplit(url)
    base, _, topic = parsed.path.rstrip("/").rpartition("/")
    if parsed.scheme not in ("http", "https") or not parsed.netloc or not topic:
        raise ConfigError(f"MONITOR_NTFY_URL={url!r} is not https://<server>/<topic>")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, base or "/", "", "")), topic


def send_ntfy(url: str, message: Mapping) -> None:
    endpoint, topic = ntfy_endpoint(url)
    payload = {
        "topic": topic,
        "title": message["title"],
        "message": message["body"],
        "priority": message["priority"],
        "tags": message["tags"],
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "devpath-monitor"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
        response.read()


def flush(
    outbox: list[dict], send: Callable[[dict], None], log: Callable[[str], None]
) -> list[dict]:
    """Deliver oldest first; stop at the first failure so order is kept. What
    is left waits for the next round, and the oldest is dropped past
    OUTBOX_LIMIT -- an outage of the notifier must not grow the state file
    without end."""
    pending = list(outbox)
    while pending:
        try:
            send(pending[0])
        except (OSError, urllib.error.URLError, http.client.HTTPException) as exc:
            log(f"Chưa gửi được thông báo ({exc}); còn {len(pending)} tin chờ lượt sau")
            break
        pending.pop(0)
    return pending[-OUTBOX_LIMIT:]


def ping_heartbeat(url: str, healthy: bool, text: str) -> None:
    """healthchecks.io-style: the URL on a good round, URL/fail on a bad one.
    A heartbeat that stops arriving is how a dead monitor, or a dead host, is
    noticed from outside."""
    target = url.rstrip("/") + ("" if healthy else "/fail")
    request = urllib.request.Request(
        target, data=text.encode("utf-8"), headers={"User-Agent": "devpath-monitor"}
    )
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
        response.read()


# --- state on disk ---------------------------------------------------------------------


def load_state(path: Path, log: Callable[[str], None]) -> State:
    try:
        return State.from_json(json.loads(path.read_text(encoding="utf-8")))
    except FileNotFoundError:
        return State()
    except (ValueError, TypeError, KeyError) as exc:
        # A state file that cannot be read costs one round of memory, not the
        # monitor: it starts over and says so.
        log(f"Bỏ tệp trạng thái hỏng {path} ({exc}), bắt đầu lại")
        return State()


def save_state(path: Path, state: State) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state.to_json(), ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


# --- the round -------------------------------------------------------------------------


def run_check(config: Config, log: Callable[[str], None] = print) -> State:
    now = datetime.now(UTC)
    state_path = config.state_dir / "state.json"
    previous = load_state(state_path, log)

    findings: dict[str, str] = {}
    readings: list[str] = []
    events: list[str] = []
    restarts = previous.restarts

    try:
        expected, containers = read_containers(config)
    except (RuntimeError, OSError, subprocess.TimeoutExpired, ValueError) as exc:
        # The daemon not answering is an incident like any other -- and the
        # web checks below still run, so the message says what users see.
        findings["docker"] = f"không đọc được trạng thái container ({exc})"
        # Not knowing is not recovering: the service problems already open
        # stay open this round instead of turning into "ổn lại" messages.
        findings.update(
            {k: p.detail for k, p in previous.problems.items() if k.startswith("service:")}
        )
    else:
        findings.update(service_findings(expected, containers))
        events, restarts = restart_events(previous.restarts, containers)
        running = sum(1 for c in containers if c.status == "running")
        readings.append(f"{running} container chạy")

    tls_problem, verified = tls_finding(config, now)
    if tls_problem:
        findings["tls"] = tls_problem
    findings.update(http_findings(config, verify=verified))
    if not tls_problem and verified:
        readings.append("TLS hợp lệ")
    if not {"site", "api", "catalog"} & findings.keys():
        readings.append("trang chủ + API + danh mục trả lời")

    disk_problem, disk_reading = disk_finding(config.disk_path, config.disk_min_free_percent)
    if disk_problem:
        findings["disk"] = disk_problem
    readings.append(disk_reading)

    state, message = evaluate(
        previous, findings, events, now, confirm_runs=config.confirm_runs, domain=config.domain
    )
    state.restarts = restarts
    state.outbox = previous.outbox + ([message.to_json()] if message else [])
    if message:
        log(f"Thông báo: {message.title} | " + message.body.replace("\n", " | "))
    if config.ntfy_url:
        queued = len(state.outbox)
        state.outbox = flush(state.outbox, lambda m: send_ntfy(config.ntfy_url, m), log)
        late = min(len(previous.outbox), queued - len(state.outbox))
        if late:
            log(f"Đã gửi bù {late} tin chờ từ lượt trước")
    else:
        state.outbox = []  # nowhere to send it; the journal line above is the record

    save_state(state_path, state)
    log(summary(findings, readings))

    if config.heartbeat_url:
        confirmed = any(p.alerted_at for p in state.problems.values())
        try:
            ping_heartbeat(config.heartbeat_url, not confirmed, summary(findings, readings))
        except (OSError, urllib.error.URLError, http.client.HTTPException) as exc:
            log(f"Không gửi được heartbeat ({exc})")
    return state


def print_status(config: Config) -> int:
    state = load_state(config.state_dir / "state.json", print)
    if state.checked_at is None:
        print(f"Chưa có lượt kiểm nào ở {config.state_dir}.")
        return 1
    checked = _parse(state.checked_at)
    age = datetime.now(UTC) - checked
    ago = "vừa xong" if age < timedelta(minutes=1) else f"{_duration(age)} trước"
    print(f"Lượt kiểm gần nhất: {_clock(checked)} ({ago})")
    if age > timedelta(minutes=5):
        print("  ! Đã lâu không có lượt nào -- timer còn chạy không?")
        print("    systemctl status devpath-monitor.timer")
    if not state.problems:
        print("Không có vấn đề nào.")
    for key, p in sorted(state.problems.items()):
        announced = "đã báo" if p.alerted_at else f"chờ xác nhận ({p.runs}/{config.confirm_runs})"
        print(f"  {label(key)}: {p.detail} -- từ {_clock(_parse(p.first_seen))}, {announced}")
    if state.outbox:
        print(f"{len(state.outbox)} thông báo chưa gửi được.")
    return 0


def send_test(config: Config) -> int:
    if not config.ntfy_url:
        print(
            "MONITOR_NTFY_URL chưa đặt trong .env.prod -- không có nơi nào để gửi.", file=sys.stderr
        )
        return 1
    message = Message(
        title="DevPath: thử thông báo",
        body=f"Nếu đọc được tin này trên điện thoại thì cảnh báo của {config.domain} đã thông.",
        priority=DEFAULT,
        tags=("bell",),
    )
    try:
        send_ntfy(config.ntfy_url, message.to_json())
    except (OSError, urllib.error.URLError, http.client.HTTPException) as exc:
        print(f"Gửi không được: {exc}", file=sys.stderr)
        return 1
    print(f"Đã gửi tới {config.ntfy_url}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("command", choices=["check", "status", "test-alert"])
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--compose-file", type=Path, default=DEFAULT_COMPOSE_FILE)
    parser.add_argument(
        "--project", default=os.environ.get("COMPOSE_PROJECT_NAME") or DEFAULT_PROJECT
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=Path(os.environ.get("MONITOR_STATE_DIR") or DEFAULT_STATE_DIR),
    )
    args = parser.parse_args(argv)

    # journald timestamps every line itself; line buffering keeps each round's
    # lines together when stdout is not a terminal. UTF-8 because the messages
    # are Vietnamese and a Windows console would otherwise refuse them.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", line_buffering=True)
    try:
        config = config_from(
            read_env_file(args.env_file),
            os.environ,
            env_file=args.env_file,
            compose_file=args.compose_file,
            state_dir=args.state_dir,
            project=args.project,
        )
    except FileNotFoundError:
        print(f"Không thấy {args.env_file}", file=sys.stderr)
        return 2
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 2

    if args.command == "status":
        return print_status(config)
    if args.command == "test-alert":
        return send_test(config)

    started = time.monotonic()
    run_check(config)
    # A round that takes most of a minute is a symptom of its own -- the next
    # tick is already due -- so it is worth a line.
    if (elapsed := time.monotonic() - started) > 40:
        print(f"Lượt kiểm mất {elapsed:.0f}s")
    # 0 whatever the round found: a failed unit means the monitor itself broke,
    # which is a different thing from the site having a problem.
    return 0


if __name__ == "__main__":
    sys.exit(main())
