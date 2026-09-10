# Attack: take the machine down by multiplying.
#
# The classic denial of service, and the one that does not need a single
# clever idea: keep forking. Without a limit this exhausts the host's process
# table and everything on the machine stops -- other people's submissions
# first, then the API, then sshd. `--pids-limit` turns it into an ordinary
# error that this program will report itself.
#
# The children sleep instead of forking again on purpose: a real bomb would
# work here too, but a test wants a number -- how many processes the cell
# allowed before it said no -- not a race.
import os
import sys
import time

started = 0
while True:
    try:
        pid = os.fork()
    except OSError as exc:
        print(f"BLOCKED  fork bomb stopped after {started} children")
        print(f"BLOCKED  the kernel refused with {type(exc).__name__}: {exc.strerror}")
        break

    if pid == 0:
        # A child that stays alive, so it keeps occupying a slot, and that
        # never returns to this loop.
        time.sleep(3600)
        os._exit(0)

    started += 1
    if started > 10_000:
        print(f"ESCAPED  forked {started} children and was never stopped")
        break

sys.stdout.flush()
