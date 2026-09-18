#!/bin/sh
# Runs on both packagers: dpkg passes "configure", rpm passes an install count.
set -eu

CONFIG=/etc/awg-keeper/agent.env
EXAMPLE=/etc/awg-keeper/agent.env.example

if command -v systemd-sysusers >/dev/null 2>&1; then
    systemd-sysusers /usr/lib/sysusers.d/awg-keeper.conf
elif ! getent passwd awgkeeper >/dev/null 2>&1; then
    useradd --system --home-dir /var/lib/awg-keeper --shell /usr/sbin/nologin \
        --comment "awg-keeper agent" awgkeeper
fi

chown root:awgkeeper /etc/awg-keeper 2>/dev/null || true
chown awgkeeper:awgkeeper /var/lib/awg-keeper 2>/dev/null || true

# An upgrade keeps the token that is already in service. Only a first install
# mints one, so the service has something to authenticate with before an
# operator has touched the host.
if [ ! -f "$CONFIG" ]; then
    umask 077
    token=$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')
    sed "s|^AWG_KEEPER_TOKEN=.*|AWG_KEEPER_TOKEN=${token}|" "$EXAMPLE" >"$CONFIG"
    # Read by systemd as root before it drops to the service user, so the
    # token needs no group at all.
    chown root:root "$CONFIG"
    chmod 0600 "$CONFIG"
    echo "awg-keeper: a token was generated in $CONFIG; the Panel needs it."
fi

if command -v systemd-tmpfiles >/dev/null 2>&1; then
    systemd-tmpfiles --create /usr/lib/tmpfiles.d/awg-keeper.conf || true
fi

if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload || true
    systemctl try-restart awg-keeper-agent.service || true
fi

echo "awg-keeper: review $CONFIG, then: systemctl enable --now awg-keeper-agent"
