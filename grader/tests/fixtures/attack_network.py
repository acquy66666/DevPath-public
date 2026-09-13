# Attack: reach the network. Any of it.
#
# A submission that can open a socket can exfiltrate the hidden test cases it
# is being graded on, fetch a solution, mine, or use the grader as a proxy for
# something the university's address gets blamed for. `--network none` leaves
# the container a loopback interface and nothing else, and every line below is
# a different way of asking whether that is really true.
import socket

socket.setdefaulttimeout(3)


def attempt(what, action):
    try:
        result = action()
    except OSError as exc:
        name = errno_name(exc)
        print(f"BLOCKED  {what:<34} {type(exc).__name__}: {name} {exc.strerror or exc}")
    except Exception as exc:  # noqa: BLE001 -- any refusal at all is a refusal
        print(f"BLOCKED  {what:<34} {type(exc).__name__}: {exc}")
    else:
        print(f"ESCAPED  {what:<34} {result!r}")


def errno_name(exc):
    import errno

    return errno.errorcode.get(exc.errno, str(exc.errno))


def connect(host, port):
    def go():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        return f"connected {host}:{port}"

    return go


# A public resolver, a public web address, and the address a Docker bridge
# usually gives the host itself -- the one that would reach the machine doing
# the grading.
attempt("TCP 8.8.8.8:53 (DNS resolver)", connect("8.8.8.8", 53))
attempt("TCP 1.1.1.1:80 (web)", connect("1.1.1.1", 80))
attempt("TCP 172.17.0.1:22 (docker host)", connect("172.17.0.1", 22))
attempt("TCP 10.0.0.1:80 (private range)", connect("10.0.0.1", 80))

attempt("DNS lookup of example.com", lambda: socket.getaddrinfo("example.com", 80))

# Raw sockets need CAP_NET_RAW, dropped with every other capability. This is
# the one that would still work if only routing had been taken away.
attempt(
    "raw socket (needs CAP_NET_RAW)",
    lambda: socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP),
)

# Listening is not an escape by itself -- nothing outside can reach it -- but
# what interfaces exist says whether the container is really alone.
print()
print("INFO     interfaces visible:", sorted(i[1] for i in socket.if_nameindex()))
