#!/bin/sh
# Bump the agent and nothing else.
#
# commitizen reads every commit since the last tag and has no way to filter by
# path, so on a monorepo it would count a commit against another sub-project.
# The increment is derived here from the commits that actually touched agent/,
# following the same map the wyld_cz plugin uses, and handed to cz.
set -eu

CZ="${CZ:-cz}"
TAG_MATCH='awg-keeper-agent-v*'

AGENT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$AGENT_DIR"

last=$(git describe --tags --abbrev=0 --match "$TAG_MATCH" 2>/dev/null || true)
if [ -n "$last" ]; then
    subjects=$(git log --format=%s "$last..HEAD" -- "$AGENT_DIR")
else
    subjects=$(git log --format=%s -- "$AGENT_DIR")
fi

if printf '%s\n' "$subjects" | grep -q '^\[feat\]'; then
    increment=MINOR
elif printf '%s\n' "$subjects" | grep -qE '^\[(fix|refactor)\]'; then
    increment=PATCH
else
    echo "agent: nothing to bump since ${last:-the first commit}."
    echo "agent: only feat, fix and refactor commits touching agent/ move it."
    exit 0
fi

echo "agent: $increment, from the commits since ${last:-the first commit}."
$CZ bump --increment "$increment" --yes "$@"
