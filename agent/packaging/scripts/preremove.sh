#!/bin/sh
# Stop the service before its binary goes away. An upgrade is not a removal:
# dpkg says "upgrade" and rpm passes 1, and neither should stop anything.
set -eu

case "${1:-}" in
upgrade | 1) exit 0 ;;
esac

if command -v systemctl >/dev/null 2>&1; then
    systemctl --no-reload disable --now awg-keeper-agent.service || true
    systemctl stop 'awg-keeper-proxy@*.socket' 'awg-keeper-proxy@*.service' || true
fi
