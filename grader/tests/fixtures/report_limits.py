"""Reports, from inside the sandbox, every limit the runner claims to apply.

A submission is the only witness that counts. The runner can pass whatever
flags it likes; what matters is what the kernel hands to the process that runs
a student's code, which is this one.
"""

import json
import os
import resource
import socket


def read(path):
    try:
        with open(path) as handle:
            return handle.read().strip()
    except OSError as error:
        return f"unreadable: {error.errno}"


def cgroup(v2_name, v1_path):
    """cgroup v2 where it exists, v1 where it does not.

    The dev machine and the CI runner are both v2; the fallback is there so a
    server on an older kernel reports numbers instead of nothing.
    """
    value = read(f"/sys/fs/cgroup/{v2_name}")
    if value.startswith("unreadable"):
        return read(v1_path)
    return value


def status_field(name):
    for line in read("/proc/self/status").splitlines():
        if line.startswith(name):
            return line.split(":", 1)[1].strip()
    return None


def write_attempt(path):
    try:
        with open(path, "w") as handle:
            handle.write("x")
    except OSError as error:
        return os.strerror(error.errno).replace(" ", "_")
    return "wrote"


print(
    json.dumps(
        {
            "pid": os.getpid(),
            "uid": os.getuid(),
            "gid": os.getgid(),
            "rlimit_cpu": resource.getrlimit(resource.RLIMIT_CPU),
            "memory_max": cgroup("memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"),
            "memory_swap_max": cgroup(
                "memory.swap.max", "/sys/fs/cgroup/memory/memory.memsw.limit_in_bytes"
            ),
            "pids_max": cgroup("pids.max", "/sys/fs/cgroup/pids/pids.max"),
            "cpu_max": cgroup("cpu.max", "/sys/fs/cgroup/cpu/cpu.cfs_quota_us"),
            "interfaces": sorted(name for _, name in socket.if_nameindex()),
            "capabilities": status_field("CapEff"),
            "no_new_privs": status_field("NoNewPrivs"),
            "rootfs_write": write_attempt("/usr/local/lib/python3.12/evil.py"),
            "tmp_write": write_attempt("/tmp/scratch"),
            "sandbox_dir": sorted(os.listdir("/sandbox")),
        }
    )
)
