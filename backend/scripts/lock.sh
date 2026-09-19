#!/bin/sh
# Re-resolve requirements.lock from pyproject.toml.
#
# One resolution for every place the backend runs (--universal): the Linux
# images, CI, and a Windows laptop, where the handful of packages that differ
# carry environment markers rather than living in a second file. Pins already in
# the lock are kept unless pyproject.toml rules them out, so this only moves
# what it has to. To move on purpose:
#
#   sh scripts/lock.sh --upgrade-package fastapi   # one package
#   sh scripts/lock.sh --upgrade                   # everything
#
# CI runs it unchanged and fails on any diff -- which is why the uv version is
# pinned: a different uv may lay out the same resolution differently.
set -eu

UV_VERSION=0.12.17

installed="$(uv --version 2>/dev/null | cut -d' ' -f2 || true)"
if [ "$installed" != "$UV_VERSION" ]; then
    echo "scripts/lock.sh needs uv $UV_VERSION (found: ${installed:-none})." >&2
    echo "    pip install uv==$UV_VERSION" >&2
    exit 1
fi

cd "$(dirname "$0")/.."
exec uv pip compile pyproject.toml \
    --extra dev \
    --universal \
    --python-version 3.12 \
    --custom-compile-command "sh scripts/lock.sh" \
    --output-file requirements.lock \
    "$@"
