"""What the grading worker may ask the Docker daemon for -- and nothing else.

A socket is not a permission system: whoever holds /var/run/docker.sock can
start a container that mounts the host's disk, joins its network or runs
privileged, which is root on the host in one request. The grading worker has
to start containers, so it cannot simply be refused the daemon. What it can be
refused is everything a grading run does not look like.

So this module is an allowlist, written from the runner's own flags
(`runner/sandbox.py`, `_container_flags`), at two levels:

  * routes. `_ping`, `containers/create`, and start / attach / wait / kill /
    inspect / remove of one container. No exec (into Postgres, say), no image
    pulls or builds, no networks, volumes, swarm or system calls.
  * contents. A create must describe a sandbox: an allowed image, the grading
    label and name, uid 10001, no network, read-only root, every capability
    dropped, no-new-privileges, memory/CPU/pids/CPU-time limits under the
    platform's ceilings, `/tmp` the only writable place, and one read-only bind
    mount of a submission directory under the grading workspace. Anything not
    named here must be at its zero value, so a field Docker adds next year is
    refused until somebody decides it is harmless.

The container-level operations are further limited to containers carrying the
grading label, which the server checks against the daemon before forwarding
(`check_owned`): a worker that could kill or remove any container could still
take the site down.

Pure functions only -- no sockets -- so every rule has a test that needs no
daemon.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from urllib.parse import parse_qs

GRADING_LABEL_KEY = "devpath.grading"
GRADING_LABEL_VALUE = "1"
SANDBOX_USER = "10001:10001"
SANDBOX_WORKDIR = "/sandbox"

#: `devpath-grading-` + uuid4().hex, exactly what the runner names containers.
CONTAINER_NAME = re.compile(r"devpath-grading-[0-9a-f]{32}")
#: The CLI names a container by what it was given for create and inspect, then
#: switches to the full id for attach, wait and start (captured from CLI 29.7:
#: docs/report/assets/phase-6/docker-socket-proxy.txt). Either way the daemon's
#: own record of the container is what `check_owned` judges.
CONTAINER_ID = re.compile(r"[0-9a-f]{64}")
#: tempfile.mkdtemp(prefix="devpath-grading-") appends 8 of [a-z0-9_].
WORKSPACE_ENTRY = re.compile(r"devpath-grading-[a-z0-9_]{8}")

#: Ceilings, a little above what the runner asks for and never above what the
#: platform lets an instructor set (`backend/app/models/grading.py`:
#: MAX_MEMORY_LIMIT_MB = 512, MAX_TIME_LIMIT_MS = 10_000).
MAX_MEMORY_BYTES = 512 * 1024 * 1024
MAX_NANO_CPUS = 1_000_000_000
MAX_PIDS = 128
MAX_CPU_SECONDS = 11  # the hard limit: 10 s of CPU plus the runner's 1 s margin
MAX_TMPFS_MB = 128
MAX_CMD_ARGS = 8
MAX_CMD_ARG_LENGTH = 4096
MAX_BODY_BYTES = 256 * 1024

API_VERSION = re.compile(r"^/v\d+\.\d+(?=/)")
SAFE_PATH = re.compile(r"^/[A-Za-z0-9._/-]*$")


class Denied(Exception):
    """The request is not one a grading run makes. The message says which rule."""


class Kind(StrEnum):
    PING = "ping"
    CREATE = "create"
    START = "start"
    ATTACH = "attach"
    WAIT = "wait"
    KILL = "kill"
    INSPECT = "inspect"
    REMOVE = "remove"


@dataclass(frozen=True)
class Route:
    kind: Kind
    #: The container the request is about; None for ping and create.
    container: str | None = None
    query: Mapping[str, list[str]] = field(default_factory=dict)

    @property
    def streams_both_ways(self) -> bool:
        """attach carries stdin up and output down on one hijacked connection."""
        return self.kind is Kind.ATTACH


@dataclass(frozen=True)
class Config:
    #: The directory submissions are written to, as the daemon sees it.
    workspace_root: str
    images: frozenset[str] = frozenset({"devpath-sandbox-python:v1"})
    #: Answers "is this exactly a real directory, no symlink anywhere in it?"
    #: for a mount source. The server passes a check against its own view of
    #: the workspace; tests pass a stub.
    is_plain_directory: Callable[[str], bool] = lambda path: True

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> Config:
        root = env.get("DEVPATH_GRADING_WORKSPACE", "").rstrip("/")
        if not root.startswith("/"):
            raise SystemExit("DEVPATH_GRADING_WORKSPACE must be an absolute path")
        images = frozenset(
            name.strip() for name in env.get("DOCKER_PROXY_IMAGES", "").split(",") if name.strip()
        )
        return cls(
            workspace_root=root,
            images=images or cls.images,
            is_plain_directory=_is_plain_directory,
        )


def _is_plain_directory(path: str) -> bool:
    """True when `path` is a directory and no component of it is a symlink.

    A compromised worker could otherwise make a submission directory a link to
    `/` and have the daemon -- which follows links when it mounts -- hand the
    host's disk to a container. This is checked at create and again at start,
    because the mount happens at start. The window between the second check and
    the daemon's mount is not closed by this; what is left behind it is a
    read-only view of files readable by uid 10001, inside a container with no
    network.
    """
    return os.path.isdir(path) and os.path.realpath(path) == path


# --- routes --------------------------------------------------------------------

_CONTAINER_ROUTE = re.compile(r"^/containers/([^/]+)(?:/(start|attach|wait|kill|json))?$")

#: Query parameters each route may carry, and nothing else.
_QUERY_KEYS: dict[Kind, frozenset[str]] = {
    Kind.PING: frozenset(),
    Kind.CREATE: frozenset({"name", "platform"}),
    Kind.START: frozenset({"detachKeys"}),
    Kind.ATTACH: frozenset({"stream", "stdin", "stdout", "stderr", "logs", "detachKeys"}),
    Kind.WAIT: frozenset({"condition"}),
    Kind.KILL: frozenset({"signal"}),
    Kind.INSPECT: frozenset({"size"}),
    # Not `link`: removing a legacy link is an operation on another container.
    Kind.REMOVE: frozenset({"force", "v"}),
}


def route(method: str, target: str) -> Route:
    """Which allowed operation `method target` is, or Denied.

    The path is matched as raw bytes against a strict character set before any
    pattern: no percent-encoding, no `..`, no doubled slashes -- nothing for
    the daemon's router to read differently from this one.
    """
    if len(target) > 2048:
        raise Denied("request target too long")
    # Split by hand, not with urlsplit: that reads `//v1.55/containers/create`
    # as a host called v1.55 and a path that looks allowed.
    path, _, raw_query = target.partition("?")
    if not SAFE_PATH.match(path) or "//" in path or "/." in path or "#" in raw_query:
        raise Denied(f"path not allowed: {path!r}")
    path = API_VERSION.sub("", path, count=1)
    try:
        query = parse_qs(raw_query, keep_blank_values=True, strict_parsing=bool(raw_query))
    except ValueError:
        raise Denied("malformed query string") from None

    kind: Kind | None = None
    container: str | None = None
    if path == "/_ping" and method in ("GET", "HEAD"):
        kind = Kind.PING
    elif path == "/containers/create" and method == "POST":
        kind = Kind.CREATE
    elif match := _CONTAINER_ROUTE.match(path):
        container, action = match.groups()
        kind = {
            ("POST", "start"): Kind.START,
            ("POST", "attach"): Kind.ATTACH,
            ("POST", "wait"): Kind.WAIT,
            ("POST", "kill"): Kind.KILL,
            ("GET", "json"): Kind.INSPECT,
            ("DELETE", None): Kind.REMOVE,
        }.get((method, action))
        if kind is not None and not (
            CONTAINER_NAME.fullmatch(container) or CONTAINER_ID.fullmatch(container)
        ):
            raise Denied(f"not a grading container name: {container!r}")
    if kind is None:
        raise Denied(f"{method} {path} is not a grading operation")

    extra = set(query) - _QUERY_KEYS[kind]
    if extra:
        raise Denied(f"query parameter not allowed for {kind}: {sorted(extra)}")
    if kind is Kind.WAIT and not set(query.get("condition", [])) <= {
        "not-running",
        "next-exit",
        "removed",
    }:
        raise Denied("wait condition not allowed")
    if kind is Kind.KILL and not all(
        re.fullmatch(r"[A-Z0-9]{1,12}", s) for s in query.get("signal", [])
    ):
        raise Denied("signal not allowed")
    return Route(kind=kind, container=container, query=query)


# --- create --------------------------------------------------------------------


def _is_zero(value: object) -> bool:
    """Docker's zero value for a field: null, "", 0, false, an empty mapping,
    or a list of nothing but zeros (the CLI sends `ConsoleSize: [0, 0]`).

    A mapping with any key is never zero, whatever its values. In Docker's JSON
    the keys are often the data: `Volumes: {"/data": {}}` is a writable volume
    and `EndpointsConfig: {"devpath_default": {}}` is a network, both with
    nothing but empty values. The first draft of this function recursed into
    mappings and let both through; the tests below the fixture caught it.
    """
    if value is None or value is False or value == "":
        return True
    if isinstance(value, bool):  # True
        return False
    if isinstance(value, int | float):
        return value == 0
    if isinstance(value, Mapping):
        return not value
    if isinstance(value, list):
        return all(_is_zero(v) for v in value)
    return False


def _fields_zero(value: object) -> bool:
    """For a struct-like object (fixed field names, not data keys): absent, or
    every field at its zero value."""
    return value is None or (
        isinstance(value, Mapping) and all(_is_zero(v) for v in value.values())
    )


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise Denied(message)


def _int(value: object, name: str) -> int:
    _need(isinstance(value, int) and not isinstance(value, bool), f"{name} must be a number")
    return value  # type: ignore[return-value]


def _check_mounts(mounts: object, config: Config) -> None:
    _need(isinstance(mounts, list) and len(mounts) == 1, "exactly one mount, the submission")
    mount = mounts[0]  # type: ignore[index]
    _need(isinstance(mount, Mapping), "mount must be an object")
    allowed = {"Type", "Source", "Target", "ReadOnly", "Consistency", "BindOptions"}
    stray = [k for k, v in mount.items() if k not in allowed and not _is_zero(v)]
    _need(not stray, f"mount fields not allowed: {stray}")
    _need(mount.get("Type") == "bind", "the mount must be a bind mount")
    _need(mount.get("Target") == SANDBOX_WORKDIR, f"the mount must target {SANDBOX_WORKDIR}")
    _need(mount.get("ReadOnly") is True, "the mount must be read-only")
    _need(_fields_zero(mount.get("BindOptions")), "bind options not allowed")
    check_mount_source(mount.get("Source"), config)


def check_mount_source(source: object, config: Config) -> None:
    """`<workspace>/devpath-grading-xxxxxxxx/code`, spelled exactly that way,
    and a real directory rather than a link to somewhere else."""
    _need(isinstance(source, str), "mount source must be a path")
    root = re.escape(config.workspace_root)
    pattern = rf"{root}/{WORKSPACE_ENTRY.pattern}/code"
    _need(
        re.fullmatch(pattern, source) is not None, f"mount source outside the workspace: {source!r}"
    )
    _need(config.is_plain_directory(source), f"mount source is not a plain directory: {source!r}")


def _check_tmpfs(tmpfs: object) -> None:
    _need(isinstance(tmpfs, Mapping) and set(tmpfs) == {"/tmp"}, "only /tmp may be a tmpfs")
    options = str(tmpfs["/tmp"]).split(",")  # type: ignore[index]
    _need({"nosuid", "nodev", "noexec"} <= set(options), "/tmp must be nosuid,nodev,noexec")
    for option in options:
        if option.startswith("size="):
            match = re.fullmatch(r"size=(\d+)m", option)
            _need(match is not None and int(match.group(1)) <= MAX_TMPFS_MB, "/tmp too large")
        else:
            _need(
                option in {"rw", "nosuid", "nodev", "noexec"}, f"tmpfs option not allowed: {option}"
            )
    _need(any(o.startswith("size=") for o in options), "/tmp must have a size")


def _check_ulimits(ulimits: object) -> None:
    _need(isinstance(ulimits, list) and len(ulimits) == 1, "exactly one ulimit, cpu")
    ulimit = ulimits[0]  # type: ignore[index]
    _need(isinstance(ulimit, Mapping) and ulimit.get("Name") == "cpu", "the ulimit must be cpu")
    soft, hard = _int(ulimit.get("Soft"), "cpu soft"), _int(ulimit.get("Hard"), "cpu hard")
    _need(0 < soft <= hard <= MAX_CPU_SECONDS, "cpu time limit out of range")


def _check_security_opts(opts: object) -> None:
    allowed = {"no-new-privileges", "no-new-privileges:true", "no-new-privileges=true"}
    _need(isinstance(opts, list) and opts, "no-new-privileges is required")
    _need(set(opts) <= allowed, f"security options not allowed: {sorted(set(opts) - allowed)}")


def _check_networking(networking: object) -> None:
    if networking is None or networking == {}:
        return
    _need(isinstance(networking, Mapping), "NetworkingConfig must be an object")
    endpoints = networking.get("EndpointsConfig") or {}  # type: ignore[union-attr]
    stray = [k for k, v in networking.items() if k != "EndpointsConfig" and not _is_zero(v)]
    _need(not stray, f"networking fields not allowed: {stray}")
    _need(isinstance(endpoints, Mapping) and set(endpoints) <= {"none"}, "only the none network")
    _need(all(_fields_zero(v) for v in endpoints.values()), "endpoint settings not allowed")


#: HostConfig fields that may be non-zero, each with what it must be. Every
#: other field must be at its zero value.
def _host_rules(config: Config) -> dict[str, Callable[[object], None]]:
    def equals(expected: object, message: str) -> Callable[[object], None]:
        return lambda value: _need(value == expected, message)

    return {
        "NetworkMode": equals("none", "the container must have no network"),
        "ReadonlyRootfs": equals(True, "the root filesystem must be read-only"),
        "CapDrop": lambda v: _need(
            isinstance(v, list) and "ALL" in [str(c).upper() for c in v],
            "every capability must be dropped",
        ),
        "SecurityOpt": _check_security_opts,
        "Memory": lambda v: _need(
            0 < _int(v, "Memory") <= MAX_MEMORY_BYTES, "memory limit out of range"
        ),
        "MemorySwap": lambda v: None,  # checked against Memory below
        "NanoCpus": lambda v: _need(
            0 < _int(v, "NanoCpus") <= MAX_NANO_CPUS, "cpu share out of range"
        ),
        "PidsLimit": lambda v: _need(
            0 < _int(v, "PidsLimit") <= MAX_PIDS, "pids limit out of range"
        ),
        "Ulimits": _check_ulimits,
        "Tmpfs": _check_tmpfs,
        "Mounts": lambda v: _check_mounts(v, config),
        "LogConfig": lambda v: _need(
            isinstance(v, Mapping) and v.get("Type") == "none" and _is_zero(v.get("Config")),
            "the container must not keep a log",
        ),
        "RestartPolicy": lambda v: _need(
            isinstance(v, Mapping)
            and v.get("Name") in ("", "no")
            and _is_zero(v.get("MaximumRetryCount")),
            "no restart policy",
        ),
        "Init": equals(True, "Init may only be switched on"),
        # -1 is "inherit the daemon's", which the CLI always sends.
        "MemorySwappiness": equals(-1, "swappiness may only be left at its default"),
    }


#: Fields where an empty list is not the default but an instruction: `[]` for
#: MaskedPaths unmasks /proc/kcore, /proc/keys and the rest the runtime hides,
#: and `[]` for ReadonlyPaths makes /proc/sys and friends writable. The
#: default is null, and null is the only value allowed.
_MUST_BE_NULL = ("MaskedPaths", "ReadonlyPaths")


#: Must be present and right, not merely allowed: a sandbox missing any of
#: these is not a sandbox.
_REQUIRED_HOST = (
    "NetworkMode",
    "ReadonlyRootfs",
    "CapDrop",
    "SecurityOpt",
    "Memory",
    "MemorySwap",
    "NanoCpus",
    "PidsLimit",
    "Ulimits",
    "Tmpfs",
    "Mounts",
    "LogConfig",
)


def _check_host(host: object, config: Config) -> None:
    _need(isinstance(host, Mapping), "HostConfig is required")
    rules = _host_rules(config)
    for key in _REQUIRED_HOST:
        _need(not _is_zero(host.get(key)), f"HostConfig.{key} is required")  # type: ignore[union-attr]
    for key in _MUST_BE_NULL:
        _need(host.get(key) is None, f"HostConfig.{key} must be left at its default")  # type: ignore[union-attr]
    for key, value in host.items():  # type: ignore[union-attr]
        if key in rules:
            if not _is_zero(value) or key in _REQUIRED_HOST:
                rules[key](value)
        elif not _is_zero(value):
            raise Denied(f"HostConfig.{key} not allowed")
    _need(host["MemorySwap"] == host["Memory"], "swap must equal memory (no swap)")  # type: ignore[index]


_ALLOWED_TOP = {
    "Image",
    "Cmd",
    "Labels",
    "User",
    "WorkingDir",
    "HostConfig",
    "NetworkingConfig",
    "AttachStdin",
    "AttachStdout",
    "AttachStderr",
    "OpenStdin",
    "StdinOnce",
    "NetworkDisabled",
}


def check_create(route_: Route, body: bytes, config: Config) -> None:
    """Denied unless the body describes a sandbox, as defined at the top."""
    names = route_.query.get("name", [])
    _need(
        len(names) == 1 and CONTAINER_NAME.fullmatch(names[0]) is not None,
        "container name must be devpath-grading-<hex>",
    )
    _need(all(p == "" for p in route_.query.get("platform", [])), "platform not allowed")
    _need(len(body) <= MAX_BODY_BYTES, "create body too large")
    try:
        spec = json.loads(body)
    except ValueError:
        raise Denied("create body is not JSON") from None
    _need(isinstance(spec, Mapping), "create body must be an object")

    stray = [k for k, v in spec.items() if k not in _ALLOWED_TOP and not _is_zero(v)]
    _need(not stray, f"fields not allowed: {sorted(stray)}")
    _need(spec.get("Image") in config.images, f"image not allowed: {spec.get('Image')!r}")
    _need(
        spec.get("Labels") == {GRADING_LABEL_KEY: GRADING_LABEL_VALUE},
        f"labels must be exactly {GRADING_LABEL_KEY}={GRADING_LABEL_VALUE}",
    )
    _need(spec.get("User") == SANDBOX_USER, f"user must be {SANDBOX_USER}")
    _need(spec.get("WorkingDir") in (None, "", SANDBOX_WORKDIR), "working directory not allowed")
    _need(spec.get("Tty") in (None, False), "no TTY")
    cmd = spec.get("Cmd")
    _need(
        isinstance(cmd, list)
        and 0 < len(cmd) <= MAX_CMD_ARGS
        and all(isinstance(a, str) and len(a) <= MAX_CMD_ARG_LENGTH for a in cmd),
        "command must be a short list of strings",
    )
    for flag in (
        "AttachStdin",
        "AttachStdout",
        "AttachStderr",
        "OpenStdin",
        "StdinOnce",
        "NetworkDisabled",
    ):
        _need(spec.get(flag) in (None, True, False), f"{flag} must be a boolean")
    _check_host(spec.get("HostConfig"), config)
    _check_networking(spec.get("NetworkingConfig"))


# --- ownership -----------------------------------------------------------------


def check_owned(inspected: Mapping, kind: Kind, config: Config) -> None:
    """Denied unless the daemon's own record of the container says it is a
    grading container -- and, before it starts, that its mount still points at
    a real submission directory (the mount happens at start, not create)."""
    labels = (inspected.get("Config") or {}).get("Labels") or {}
    _need(labels.get(GRADING_LABEL_KEY) == GRADING_LABEL_VALUE, "not a grading container")
    name = str(inspected.get("Name", "")).lstrip("/")
    _need(CONTAINER_NAME.fullmatch(name) is not None, "not a grading container")
    if kind is Kind.START:
        mounts = inspected.get("Mounts") or []
        _need(len(mounts) == 1, "a grading container has exactly one mount")
        check_mount_source(mounts[0].get("Source"), config)
