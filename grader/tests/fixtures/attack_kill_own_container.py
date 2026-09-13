# Attack: end the run rather than fail it.
#
# The honest limitation, and the one an examiner asks about first: a
# submission cannot be stopped from killing its own container. SIGKILL to
# PID 1 is discarded -- the kernel protects the init of a namespace from its
# own children -- but SIGTERM is a signal `docker-init` handles, and handling
# it means shutting the container down.
#
# What matters is the blast radius. The signal cannot leave this PID
# namespace, so no other submission and nothing on the host is touched, and
# the container comes back non-zero, so the run is a runtime error rather than
# an accepted one. A student can throw their own submission away. That is all.
import os
import time

print("still here, about to signal PID 1")
os.kill(1, 15)

# Not instant: the signal goes to init, which shuts down and takes this
# process with it. Waiting is what makes the outcome a fact rather than a
# race -- and it costs no CPU, so the time limit stays out of it.
time.sleep(10)

print("ESCAPED  still running ten seconds after SIGTERM to PID 1")
