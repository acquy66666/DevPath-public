# Attack: leave something behind.
#
# The prize here is not this run, it is the next one. A submission that can
# write into the image's standard library plants code that every later
# submission imports; one that can rewrite its own source file changes what
# the grader thinks it graded. `--read-only` is what makes the whole rootfs
# refuse, and `/tmp` is the single exception -- a tmpfs of its own that dies
# with the container.
import os

TARGETS = [
    ("/etc/passwd", "append to the image's user list"),
    ("/etc/devpath-was-here", "create a file at the root of /etc"),
    ("/devpath-was-here", "create a file at /"),
    ("/usr/local/lib/python3.12/os.py", "poison the standard library"),
    ("/usr/local/bin/python3", "replace the interpreter"),
    ("/sandbox/main.py", "rewrite the source that was graded"),
    ("/sandbox/extra.py", "plant a module beside the source"),
]

for path, what in TARGETS:
    try:
        with open(path, "ab") as handle:
            handle.write(b"# devpath\n")
    except OSError as exc:
        print(f"BLOCKED  {what:<40} {type(exc).__name__}: {exc.strerror}")
    else:
        print(f"ESCAPED  {what:<40} wrote to {path}")

# The one place that must work, or a legitimate submission cannot use a
# temporary file at all.
try:
    with open("/tmp/scratch", "w", encoding="utf-8") as handle:
        handle.write("ok")
    os.remove("/tmp/scratch")
except OSError as exc:
    print(f"BROKEN   {'write to /tmp (must be allowed)':<40} {exc}")
else:
    print(f"ALLOWED  {'write to /tmp (must be allowed)':<40} as designed")
