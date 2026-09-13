# Attack: read something that was never meant for this submission.
#
# Three kinds of prize, and the container has to deny all three: the host that
# does the grading, the platform's own secrets, and the exercise's hidden test
# data. The container's own `/etc/passwd` is not a prize -- it belongs to the
# image and describes nobody -- but `/var/run/docker.sock` is the whole game,
# because a submission that can talk to the daemon can start a container
# without any of these limits.
import os

INTERESTING = [
    # The escape hatch. Its absence is not a nicety; it is the reason a
    # sandbox escape is not one line of Python.
    "/var/run/docker.sock",
    "/run/docker.sock",
    # The host's disks, if any were handed through.
    "/dev/sda",
    "/dev/vda",
    "/dev/mem",
    "/dev/kmsg",
    # Kernel memory, and the host's own view of its processes.
    "/proc/kcore",
    "/proc/sysrq-trigger",
    # Shadow passwords of the image: readable only by root, so this is the
    # test that says we are not root.
    "/etc/shadow",
    # Places a careless bind mount would land.
    "/host",
    "/mnt/host",
    "/media",
    # The platform's own configuration, if the worker's environment leaked in.
    "/app/.env",
    "/backend/.env",
    # The runner's scratch directory sits outside the mount on purpose: the
    # test input the submission is meant to solve blind is written there.
    "/sandbox/stdin",
    "/sandbox/../stdin",
    "/sandbox/expected",
]

DEV_NULL = os.stat("/dev/null").st_rdev


def describe_empty(path):
    """Opening a file and getting nothing is not the same as being refused.

    Docker replaces the dangerous entries in `/proc` with a bind mount of
    `/dev/null`, so the open succeeds and the read comes back empty. Saying so
    -- and proving it by the device number -- is more honest than calling it a
    refusal, and it names a third layer of defence that neither the image nor
    the runner flags provide.
    """
    if os.stat(path).st_rdev == DEV_NULL:
        return f"MASKED   {path:<26} replaced by /dev/null, nothing to read"
    return f"EMPTY    {path:<26} readable but holds nothing"


for path in INTERESTING:
    try:
        with open(path, "rb") as handle:
            head = handle.read(64)
    except FileNotFoundError:
        print(f"BLOCKED  {path:<26} does not exist")
    except PermissionError as exc:
        print(f"BLOCKED  {path:<26} PermissionError: {exc.strerror}")
    except IsADirectoryError:
        # A place a careless bind mount would have landed. Saying it is a
        # directory is not the point; saying there is nothing in it is.
        print(f"BLOCKED  {path:<26} an empty directory: {sorted(os.listdir(path))}")
    except OSError as exc:
        print(f"BLOCKED  {path:<26} {type(exc).__name__}: {exc.strerror}")
    else:
        print(describe_empty(path) if not head else f"ESCAPED  {path:<26} read {head[:32]!r}")

print()
# Everything the submission was given. One file, the one it wrote itself.
print("INFO     contents of the mount:", sorted(os.listdir("/sandbox")))

# The environment the worker runs in must not travel into the container: it is
# where the database URL, the Gemini key and the JWT secret live. What is left
# is furniture from the base image and the four settings our own Dockerfile
# adds -- constants of the image, identical for every submission, none of them
# a secret. (`GPG_KEY` reads alarmingly and is not: it is the public key
# python.org signs its releases with.)
FURNITURE = {
    "PATH", "HOSTNAME", "HOME", "LANG", "PWD",
    "GPG_KEY", "PYTHON_VERSION", "PYTHON_SHA256",
    "PYTHONDONTWRITEBYTECODE", "PYTHONHASHSEED", "PYTHONIOENCODING", "PYTHONUNBUFFERED",
}
print("INFO     environment:", sorted(os.environ))
brought_in = sorted(set(os.environ) - FURNITURE)
print("INFO     environment variables that are not image furniture:", brought_in)

# Other people's processes. With --init the submission is a child of a tiny
# init and should see nothing but itself.
pids = sorted(int(entry) for entry in os.listdir("/proc") if entry.isdigit())
print("INFO     processes visible:", pids)
