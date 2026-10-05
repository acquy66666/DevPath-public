#!/usr/bin/env python3
"""Do the .env.example files still describe what the code reads?

    python3 infra/scripts/check_env_examples.py     (needs `docker compose`)

Four checks, each one a way the examples have drifted before or could:

  1. every ${VAR} in docker-compose.yml is in infra/.env.example
  2. every ${VAR} in docker-compose.prod.yml is in infra/.env.prod.example
  3. every variable the dev stack hands an application container, the
     production stack hands it too -- unless it is listed below as dev-only,
     with the reason. This is the one that matters: VNPAY_* was set for the
     backend in development and simply absent in production, so payments on
     the VPS would have answered 503 whatever .env.prod said. Nothing else
     would have caught it before a real purchase did.
  4. every key in backend/.env.example is a field of Settings, and every key
     in frontend/.env.example is read somewhere in the frontend -- an example
     that names a variable nothing reads sends someone looking for a switch
     that does not exist.

Standard library only; run by CI's deploy-config job.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INFRA = ROOT / "infra"

#: Set in development, deliberately not in production. Each needs a reason.
DEV_ONLY = {
    # Polling file watchers for bind mounts from Windows; production has no
    # bind mounts and no reloader.
    "WATCHFILES_FORCE_POLLING": "no reloader in production",
    "WATCH_POLL_INTERVAL_MS": "no dev server in production",
    # Empty in production on purpose: the browser calls /api on its own
    # origin and nginx routes it (docker-compose.prod.yml, frontend build).
    "NEXT_PUBLIC_API_BASE_URL": "same-origin /api behind nginx",
    # The backup service's fallback to the dev stack's storage. Production
    # backups go off the machine, and there the service refuses to guess.
    "STORAGE_ACCESS_KEY": "backup falls back to the dev storage only",
    "STORAGE_SECRET_KEY": "backup falls back to the dev storage only",
}

#: Read by something other than compose: nginx's own entrypoint script.
NOT_IN_EXAMPLES = {"NGINX_LOCAL_RESOLVERS"}

KEY = re.compile(r"^\s*#?\s*([A-Z][A-Z0-9_]+)=", re.MULTILINE)
COMPOSE_VAR = re.compile(r"\$\{([A-Z][A-Z0-9_]*)")


def example_keys(path: Path) -> set[str]:
    """Keys an example documents, commented-out ones included -- a commented
    default is still documentation."""
    return set(KEY.findall(path.read_text(encoding="utf-8")))


def compose_vars(path: Path) -> set[str]:
    return set(COMPOSE_VAR.findall(path.read_text(encoding="utf-8"))) - NOT_IN_EXAMPLES


def rendered(path: Path) -> dict:
    out = subprocess.run(
        ["docker", "compose", "-f", str(path), "config", "--no-interpolate", "--format", "json"],
        capture_output=True,
        encoding="utf-8",
        check=True,
    ).stdout
    return json.loads(out)["services"]


def handed_over(service: dict) -> set[str]:
    """What a container is given: its environment, plus build args -- the
    production frontend takes NEXT_PUBLIC_* at build time, not at run time."""
    env = set((service.get("environment") or {}).keys())
    build = service.get("build")
    if isinstance(build, dict):
        env |= set((build.get("args") or {}).keys())
    return env


def settings_fields(config: Path) -> set[str]:
    tree = ast.parse(config.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Settings":
            return {
                stmt.target.id.upper()
                for stmt in node.body
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
            }
    raise SystemExit(f"No Settings class in {config}")


def frontend_reads(frontend: Path) -> set[str]:
    names: set[str] = set()
    for path in frontend.rglob("*"):
        if any(part in {"node_modules", ".next"} for part in path.parts):
            continue
        if path.suffix in {".ts", ".tsx", ".js", ".mjs"} and path.is_file():
            names |= set(re.findall(r"process\.env\.([A-Z][A-Z0-9_]*)", path.read_text("utf-8")))
    return names


def main() -> int:
    problems: list[str] = []

    for compose, example in (
        ("docker-compose.yml", ".env.example"),
        ("docker-compose.prod.yml", ".env.prod.example"),
    ):
        missing = compose_vars(INFRA / compose) - example_keys(INFRA / example)
        if missing:
            problems.append(f"infra/{compose} reads {sorted(missing)}, not in infra/{example}")

    dev, prod = rendered(INFRA / "docker-compose.yml"), rendered(INFRA / "docker-compose.prod.yml")
    for name in sorted(dev.keys() & prod.keys()):
        lost = handed_over(dev[name]) - handed_over(prod[name]) - DEV_ONLY.keys()
        if lost:
            problems.append(
                f"service {name}: the dev stack sets {sorted(lost)}, production does not "
                "(add them to docker-compose.prod.yml, or to DEV_ONLY here with a reason)"
            )

    fields = settings_fields(ROOT / "backend/app/core/config.py")
    unknown = example_keys(ROOT / "backend/.env.example") - fields
    if unknown:
        problems.append(f"backend/.env.example names {sorted(unknown)}, which Settings lacks")

    unread = example_keys(ROOT / "frontend/.env.example") - frontend_reads(ROOT / "frontend")
    if unread:
        problems.append(f"frontend/.env.example names {sorted(unread)}, which nothing reads")

    for problem in problems:
        print(f"✗ {problem}", file=sys.stderr)
    if not problems:
        print(f"✓ env examples match the code ({len(dev)} dev, {len(prod)} production services)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
