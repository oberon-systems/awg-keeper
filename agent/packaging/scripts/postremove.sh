#!/bin/sh
# The user, the token and the state are deliberately left behind: a removal is
# not a decision to destroy the credentials a Panel is still configured with.
set -eu

if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload || true
fi
