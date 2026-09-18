# Catches the CPU limit's warning and keeps burning, so only the hard limit's
# SIGKILL ends it: a real time limit that exits 137, like a memory kill does.
import signal

signal.signal(signal.SIGXCPU, lambda *_: None)
while True:
    pass
