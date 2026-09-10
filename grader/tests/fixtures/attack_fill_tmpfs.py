# Attack: fill the disk of the machine doing the grading.
#
# `/tmp` has to be writable -- plenty of legitimate exercises use a temporary
# file -- which makes it the one door left open, and a door is enough if what
# is behind it is the host's disk. It is not: `/tmp` is a tmpfs with a size of
# its own, so this program runs out of room long before anything outside the
# container notices, and every byte it wrote disappears when the container does.
import os

CHUNK = b"x" * (1024 * 1024)
written = 0

try:
    with open("/tmp/flood", "wb") as flood:
        while written < 4096:  # 4 GB would be plenty to hurt a small VPS
            flood.write(CHUNK)
            flood.flush()
            os.fsync(flood.fileno())
            written += 1
except OSError as exc:
    print(f"BLOCKED  ran out of room after {written} MB written to /tmp")
    print(f"BLOCKED  the kernel refused with {type(exc).__name__}: {exc.strerror}")
else:
    print(f"ESCAPED  wrote {written} MB to /tmp and was never stopped")
