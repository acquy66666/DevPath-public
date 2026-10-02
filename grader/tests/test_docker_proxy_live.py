"""The Docker proxy in front of a real daemon: grading works, and the things a
holder of the raw socket could do do not.

Runs only when the environment says the Docker CLI is pointed at the proxy
(`DEVPATH_THROUGH_PROXY=1`, `DOCKER_HOST=tcp://...`) -- CI's second grader
pass, or inside the grading worker. The verdict and sandbox-attack suites run
in that same pass, so "the runner still works through the proxy" is proven by
all of them, not by the one sanity check here.

What these add is the attacker's view: someone with code execution in the
grading worker, trying the requests that made the raw socket root on the host.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import uuid
from pathlib import Path

import pytest

from runner.images import PYTHON_IMAGE
from runner.sandbox import (
    DEFAULT_LIMITS,
    GRADING_LABEL,
    Outcome,
    _container_flags,
    execute,
    workspace_root,
)

pytestmark = [
    pytest.mark.skipif(
        not os.environ.get("DEVPATH_THROUGH_PROXY"), reason="needs DOCKER_HOST pointed at the proxy"
    ),
    pytest.mark.usefixtures("sandbox_images"),
]

REAL_HOST = os.environ.get("DEVPATH_REAL_DOCKER_HOST")
needs_real_host = pytest.mark.skipif(
    not REAL_HOST, reason="needs DEVPATH_REAL_DOCKER_HOST to set up a container to attack"
)


def docker(*args: str, host: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *(["--host", host] if host else []), *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def refused(result: subprocess.CompletedProcess[str], reason: str = "") -> None:
    assert result.returncode != 0, result.stdout
    assert "devpath-docker-proxy" in result.stderr, result.stderr
    assert reason in result.stderr, result.stderr


def grading_name() -> str:
    return f"devpath-grading-{uuid.uuid4().hex}"


def test_a_submission_is_graded_through_the_proxy() -> None:
    result = execute("print(int(input()) * 2)", stdin="21\n")
    assert result.outcome is Outcome.EXITED, result.system_error
    assert result.stdout == "42\n"


@pytest.mark.parametrize(
    "args",
    [
        ["run", "--rm", "--privileged", PYTHON_IMAGE, "true"],
        ["run", "--rm", "-v", "/:/host", PYTHON_IMAGE, "true"],
        ["run", "--rm", "--network", "host", PYTHON_IMAGE, "true"],
        ["ps", "--all"],
        ["images"],
        ["pull", "alpine:3"],
        ["info"],
        ["network", "ls"],
        ["volume", "create", "devpath-proxy-test"],
        ["exec", "devpath-postgres-1", "true"],
        ["system", "prune", "--force"],
    ],
)
def test_what_made_the_raw_socket_root_on_the_host_is_refused(args: list[str]) -> None:
    refused(docker(*args))


def test_a_grading_shaped_create_with_the_host_root_mounted_is_refused() -> None:
    """Every runner flag, exactly, except the mount source."""
    flags = _container_flags(grading_name(), Path("/"), DEFAULT_LIMITS)
    refused(docker("create", *flags, PYTHON_IMAGE, "true"), "outside the workspace")


def test_a_submission_directory_that_is_a_link_to_the_host_root_is_refused() -> None:
    workspace = Path(tempfile.mkdtemp(prefix="devpath-grading-", dir=workspace_root()))
    try:
        (workspace / "code").symlink_to("/")
        flags = _container_flags(grading_name(), workspace / "code", DEFAULT_LIMITS)
        refused(docker("create", *flags, PYTHON_IMAGE, "true"), "not a plain directory")
    finally:
        (workspace / "code").unlink()
        workspace.rmdir()


def test_a_link_swapped_in_after_create_is_caught_at_start() -> None:
    """The daemon mounts at start, not create -- so that is where it is
    checked again."""
    workspace = Path(tempfile.mkdtemp(prefix="devpath-grading-", dir=workspace_root()))
    name = grading_name()
    code = workspace / "code"
    code.mkdir()
    try:
        flags = _container_flags(name, code, DEFAULT_LIMITS)
        created = docker("create", *flags, PYTHON_IMAGE, "true")
        assert created.returncode == 0, created.stderr
        code.rename(workspace / "code.real")
        code.symlink_to("/")
        refused(docker("start", name), "not a plain directory")
    finally:
        docker("rm", "--force", name)
        if code.is_symlink():
            code.unlink()
        if (workspace / "code.real").exists():
            (workspace / "code.real").rmdir()
        workspace.rmdir()


@needs_real_host
def test_a_container_that_is_not_a_grading_run_cannot_be_touched() -> None:
    """Set up behind the proxy's back with the real socket: one ordinary
    container, and one named like a grading run but without the label."""
    victim = f"devpath-proxy-victim-{uuid.uuid4().hex[:8]}"
    impostor = grading_name()
    sleeper = ["python3", "-c", "import time; time.sleep(120)"]
    started = []
    try:
        for name in (victim, impostor):
            run = docker("run", "-d", "--name", name, PYTHON_IMAGE, *sleeper, host=REAL_HOST)
            assert run.returncode == 0, run.stderr
            started.append(name)
        victim_id = docker("inspect", "--format", "{{.Id}}", victim, host=REAL_HOST).stdout.strip()

        refused(docker("kill", victim), "not a grading container name")
        refused(docker("kill", victim_id), "not a grading container")
        refused(docker("rm", "--force", victim_id), "not a grading container")
        refused(docker("kill", impostor), "not a grading container")
        alive = docker(
            "inspect", "--format", "{{.State.Running}}", victim, impostor, host=REAL_HOST
        )
        assert alive.stdout.split() == ["true", "true"]
    finally:
        for name in started:
            docker("rm", "--force", name, host=REAL_HOST)


@needs_real_host
def test_nothing_is_left_behind_by_the_refused_attempts() -> None:
    left = docker("ps", "--all", "--quiet", "--filter", f"label={GRADING_LABEL}", host=REAL_HOST)
    assert left.returncode == 0
    assert left.stdout.strip() == ""
