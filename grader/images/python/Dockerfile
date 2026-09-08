# The Python sandbox: the image that runs code written by strangers.
#
# It is deliberately dull. Everything a normal application image wants -- a
# package manager, a writable home, a login shell, a few convenient libraries
# -- is either absent or unreachable, because none of it is needed to run one
# file against one stdin, and every one of them is something a submission
# could try to use.
#
# The container flags matter as much as this file does (network none, memory,
# pids, read-only, cap-drop ALL, no-new-privileges) and belong to the runner.
# What lives here is the half that survives a runner with a missing flag; the
# tests in grader/tests/test_python_image.py check both halves separately for
# exactly that reason.
#
# The base is pinned to a minor version rather than a digest: patch rebuilds
# should arrive with a plain `docker build`, and the tests re-run on every
# build are what notice if a new base brings back something stripped here.

FROM python:3.12-slim-bookworm

# An identity of our own rather than the shared `nobody` (65534). A fixed uid
# in our own range is the number the worker will chown the mounted submission
# to, and `nobody` is exactly the uid that other things on a host already map
# to -- most notably a squashed NFS user. Two unrelated processes sharing an
# identity is a coincidence to avoid, not to rely on.
#
# The shell is nologin and the home directory is /tmp, the one path that is
# writable at runtime and only because the runner mounts a tmpfs there.
RUN groupadd --system --gid 10001 sandbox \
    && useradd --system --uid 10001 --gid 10001 \
        --home-dir /tmp --shell /usr/sbin/nologin sandbox

RUN set -eux; \
    \
# No pip, no ensurepip, and an empty site-packages. There is no network to
# install from anyway, so this is not about stopping a download: it is about
# the image being the standard library and nothing else, today and after the
# next base bump. That is what makes a verdict reproducible -- the same
# submission cannot pass in September and fail in November because a package
# arrived underneath it.
    rm -rf /usr/local/lib/python3.12/ensurepip; \
    find /usr/local/lib/python3.12/site-packages -mindepth 1 -maxdepth 1 -exec rm -rf {} +; \
    rm -f /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.12 \
        /usr/local/bin/wheel /usr/local/bin/easy_install; \
    \
# Strip every setuid and setgid bit in the image. `--cap-drop ALL` and
# no-new-privileges already make these inert, but both of those are flags on
# somebody else's command line, and this is not.
    find / -xdev -type f -perm /6000 -exec chmod a-s {} +; \
    \
# Where the runner mounts the submission, read-only, and where it runs. Owned
# by root at mode 555 so the program cannot write a file next to its own
# source even if the mount were ever made writable.
    mkdir -p /sandbox; \
    chown root:root /sandbox; \
    chmod 555 /sandbox

ENV LANG=C.UTF-8 \
    # Submitted output is compared byte for byte and the courses are in
    # Vietnamese, so a C locale answering in ASCII would fail correct
    # solutions.
    PYTHONIOENCODING=utf-8 \
    # A program killed at its time limit never gets to flush. Unbuffered means
    # the output it did produce has already reached the grader.
    PYTHONUNBUFFERED=1 \
    # The rootfs is read-only; without this Python tries to write .pyc files
    # next to the source on every single run and quietly fails each time.
    PYTHONDONTWRITEBYTECODE=1 \
    # Fixed, so the iteration order of a set is the same on every run. With
    # the default per-process randomisation, one submission printing a set
    # would be AC or WA depending on which worker picked it up.
    PYTHONHASHSEED=0 \
    HOME=/tmp

WORKDIR /sandbox

# The runner passes `--user` as well. This is the copy of that decision that
# cannot be left off a command line.
USER sandbox

# The runner always supplies the whole command; this is only what `docker run`
# with no arguments does, and it does nothing interesting.
CMD ["python3", "--version"]
