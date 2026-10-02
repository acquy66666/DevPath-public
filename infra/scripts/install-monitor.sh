#!/usr/bin/env bash
#
# Install the host monitor (infra/monitor/) as a systemd timer: a round every
# minute, from boot, as the user who ran sudo.
#
#   sudo ./scripts/install-monitor.sh            # install, start, run one round now
#   sudo ./scripts/install-monitor.sh --remove   # stop it and remove the units
#
# Run again after moving the checkout: the units point at this directory.
# Where alerts go is MONITOR_NTFY_URL in .env.prod, read on every round, so
# changing it needs no reinstall. Then prove it reaches the phone:
#
#   python3 monitor/devpath_monitor.py test-alert
set -euo pipefail

cd "$(dirname "$0")/.."
infra="$(pwd)"
units=(devpath-monitor.service devpath-monitor.timer)

if [[ "${EUID}" -ne 0 ]]; then
    echo "Needs root to write /etc/systemd/system: sudo $0 $*" >&2
    exit 1
fi

if [[ "${1:-}" == "--remove" ]]; then
    systemctl disable --now devpath-monitor.timer 2>/dev/null || true
    for unit in "${units[@]}"; do
        rm -f "/etc/systemd/system/${unit}"
    done
    systemctl daemon-reload
    echo "Removed. The last state is still in /var/lib/devpath-monitor."
    exit 0
fi

# The deploying user, not root: the monitor needs the docker group and
# nothing else. MONITOR_USER overrides it for a machine where sudo is not how
# you got here (CI runs it that way).
user="${MONITOR_USER:-${SUDO_USER:-}}"
if [[ -z "${user}" || "${user}" == root ]]; then
    echo "Run it with sudo from the user that deploys (or set MONITOR_USER)." >&2
    exit 1
fi
if ! id -nG "${user}" | tr ' ' '\n' | grep -qx docker; then
    echo "${user} is not in the docker group, so it cannot read container state." >&2
    exit 1
fi
if [[ "${infra}" =~ [[:space:]] ]]; then
    echo "The checkout path has a space in it, which a unit's ExecStart cannot take: ${infra}" >&2
    exit 1
fi
if [[ ! -f .env.prod ]]; then
    echo "No infra/.env.prod. The monitor reads DOMAIN and MONITOR_* from it." >&2
    exit 1
fi
if [[ ! -x /usr/bin/python3 ]]; then
    echo "No /usr/bin/python3 -- Ubuntu ships one; something is unusual here." >&2
    exit 1
fi

echo "==> Installing units for ${user}, pointing at ${infra}"
for unit in "${units[@]}"; do
    sed -e "s|@INFRA@|${infra}|g" -e "s|@USER@|${user}|g" \
        "monitor/${unit}" > "/etc/systemd/system/${unit}"
done
systemctl daemon-reload
systemctl enable --now devpath-monitor.timer

echo "==> One round now"
# A oneshot unit: `start` returns when the round has finished, and fails if
# the monitor itself did -- not if it found a problem with the site.
systemctl start devpath-monitor.service
journalctl -u devpath-monitor.service -n 3 --no-pager -o cat

echo
systemctl list-timers devpath-monitor.timer --no-pager
if ! grep -qE '^MONITOR_NTFY_URL=.+' .env.prod; then
    echo
    echo "MONITOR_NTFY_URL is empty: rounds run and log, but nothing is sent anywhere."
fi
