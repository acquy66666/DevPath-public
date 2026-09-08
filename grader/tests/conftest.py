"""Fixtures shared by the grader tests.

Everything here needs a real Docker daemon. What is under test is a container
image and the isolation the kernel gives it, and neither of those can be
stood in for by a mock -- a mocked sandbox proves only that the mock is safe.
"""

from __future__ import annotations

import os
import shutil
import subprocess

import pytest

from runner.images import build_all


def _docker_is_running() -> bool:
    if shutil.which("docker") is None:
        return False
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0


@pytest.fixture(scope="session", autouse=True)
def sandbox_images() -> None:
    """Build the images once per run, from the same code the worker will use.

    Missing Docker is a local inconvenience and a CI failure, the same rule the
    backend suite follows: skipping in CI would turn "the sandbox was never
    tested" into a green tick, which is the one outcome this suite exists to
    prevent.
    """
    if not _docker_is_running():
        if os.environ.get("CI"):
            pytest.fail("Docker is not available. In CI that is a failure, not a skip.")
        pytest.skip("Docker is not running -- start it to test the sandbox image.")

    build_all()
