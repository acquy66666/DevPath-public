# Attack: stop being uid 10001.
#
# Everything else in this suite assumes the submission is an unprivileged user
# with no capabilities. This is the file that tests the assumption itself. Two
# independent locks have to hold: every capability is dropped, so the calls
# below have no permission to succeed, and `no-new-privileges` means nothing
# the program executes can gain any -- which is what makes the absence of
# setuid binaries in the image a second wall rather than the only one.
import ctypes
import os
import time

libc = ctypes.CDLL(None, use_errno=True)


def attempt(what, action):
    try:
        result = action()
    except Exception as exc:  # noqa: BLE001 -- any refusal at all is a refusal
        print(f"BLOCKED  {what:<38} {type(exc).__name__}: {exc}")
    else:
        print(f"ESCAPED  {what:<38} {result!r}")


def syscall(name, *args):
    """Call libc directly, because Python hides some of these behind checks."""

    def go():
        ctypes.set_errno(0)
        rc = getattr(libc, name)(*args)
        if rc != 0:
            err = ctypes.get_errno()
            raise OSError(err, os.strerror(err))
        return f"{name} returned {rc}"

    return go


print(f"INFO     running as uid={os.getuid()} gid={os.getgid()} euid={os.geteuid()}")
print()

attempt("become root with setuid(0)", lambda: os.setuid(0))
attempt("become root with setgid(0)", lambda: os.setgid(0))
attempt("become root with setresuid(0,0,0)", syscall("setresuid", 0, 0, 0))
attempt("chroot('/') (needs CAP_SYS_CHROOT)", lambda: os.chroot("/"))
attempt(
    "mount a tmpfs (needs CAP_SYS_ADMIN)",
    syscall("mount", b"none", b"/tmp", b"tmpfs", 0, None),
)
attempt(
    "mknod a block device (CAP_MKNOD)",
    lambda: os.mknod("/tmp/disk", 0o600 | 0o60000, os.makedev(8, 0)),
)
attempt("raise the CPU limit that binds us", lambda: __import__("resource").setrlimit(
    __import__("resource").RLIMIT_CPU, (3600, 3600)
))
attempt("write to /proc/sys/kernel/hostname", lambda: open("/proc/sys/kernel/hostname", "w"))


def sigkill_pid_1():
    """Whether the syscall was allowed is the wrong question.

    `kill(1, SIGKILL)` from inside the namespace returns success and does
    nothing: the kernel marks the init of a PID namespace unkillable by its
    own children, so the signal is discarded rather than refused. Reporting
    the return value would call this an escape; reporting whether PID 1 is
    still there reports what happened.
    """
    os.kill(1, 9)
    time.sleep(0.2)
    with open("/proc/1/comm", encoding="utf-8") as comm:
        survivor = comm.read().strip()
    what = "SIGKILL to PID 1 of this container"
    if os.path.exists("/proc/1"):
        print(f"BLOCKED  {what:<38} allowed, ignored: PID 1 ({survivor}) is still running")
    else:
        print(f"ESCAPED  {what:<38} PID 1 is gone")


sigkill_pid_1()

print()
# The kernel's own answer, which no amount of Python can talk its way around.
ANSWERED_BY_THE_KERNEL = (
    "Uid:", "Gid:", "CapEff:", "CapPrm:", "CapBnd:", "NoNewPrivs:", "Seccomp:",
)
with open("/proc/self/status", encoding="utf-8") as status:
    for line in status:
        if line.startswith(ANSWERED_BY_THE_KERNEL):
            print("INFO    ", line.rstrip())
