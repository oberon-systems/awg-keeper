#!/usr/bin/env bash
set -euo pipefail

stack="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The host port the panel is published on; compose reads it from here.
export LISTEN_PORT="${LISTEN_PORT:-8000}"
panel="http://127.0.0.1:$LISTEN_PORT"
agent="http://127.0.0.1:8081"

# No --env-file and no .env beside the compose file: the only thing compose
# substitutes is LISTEN_PORT from this environment, and nothing it can mangle.
compose() {
    docker compose --project-directory "$stack" "$@"
}

fail() {
    echo "$*" >&2
    exit 1
}

wait_for() {
    local seconds="$1"
    shift
    until "$@"; do
        seconds=$((seconds - 1))
        if [ "$seconds" -le 0 ]; then return 1; fi
        sleep 1
    done
}

# Half a stand is worse than none: anything that fails after compose is up
# takes the stand down with it.
rollback() {
    local status=$?
    echo "kickstart failed, stopping the stand" >&2
    compose down --remove-orphans
    exit "$status"
}

# Everything the stand runs is built from this tree every time. Docker caches
# its layers, so an unchanged tree costs a moment - while an image kept
# because it merely exists is a stand running code nobody has in front of them.
kickstart() {
    compose build
    compose up -d
    trap rollback EXIT
    if ! wait_for 30 curl -fs -o /dev/null "$panel/api/v1/ping"; then
        compose logs --tail 20 panel >&2
        fail "the panel did not answer at $panel/api/v1/ping"
    fi
    if ! wait_for 10 curl -fs -o /dev/null "$agent/v1/health"; then
        compose logs --tail 20 agent >&2
        fail "the agent did not answer at $agent/v1/health"
    fi
    trap - EXIT
    cat <<REPORT

panel $panel     admin / admin
agent $agent/v1/health

awg0 and awg1 come up discovered and disabled, which is the real behaviour:
give one an endpoint host and enable it before issuing a profile.

The stand keeps nothing. Everything it did is gone after make down.
REPORT
}

# There is no state to remove, so down is the whole of clean.
down() {
    compose down --remove-orphans
}

# The panel's and the agent's python are mounted in, so a change to either is
# one restart away; the browser interface is built into the image and is not.
restart() {
    compose restart
}

logs() {
    compose logs -f
}

# The stand-in binaries append their argv inside the agent container, which is
# the quickest way to see what the panel actually asked the host to do.
calls() {
    compose exec -T agent sh -c 'echo "--- awg"; cat /host/awg.log; echo "--- xray"; cat /host/xray.log'
}

case "${1:-kickstart}" in
kickstart) kickstart ;;
down) down ;;
restart) restart ;;
logs) logs ;;
calls) calls ;;
*) fail "usage: kickstart.sh [kickstart|down|restart|logs|calls]" ;;
esac
