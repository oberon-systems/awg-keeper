#!/bin/sh
# Bump the panel and nothing else.
#
# commitizen reads every commit since the last tag and has no way to filter by
# path, so on a monorepo it would count a commit against another sub-project.
# The increment is derived here from the commits that actually touched web/,
# following the same map the wyld_cz plugin uses, and handed to cz.
set -eu

CZ="${CZ:-cz}"
TAG_MATCH='awg-keeper-web-v*'

PANEL_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$PANEL_DIR"

last=$(git describe --tags --abbrev=0 --match "$TAG_MATCH" 2>/dev/null || true)
if [ -n "$last" ]; then
    subjects=$(git log --format=%s "$last..HEAD" -- "$PANEL_DIR")
else
    subjects=$(git log --format=%s -- "$PANEL_DIR")
fi

if printf '%s\n' "$subjects" | grep -q '^\[feat\]'; then
    increment=MINOR
elif printf '%s\n' "$subjects" | grep -qE '^\[(fix|refactor)\]'; then
    increment=PATCH
else
    echo "panel: nothing to bump since ${last:-the first commit}."
    echo "panel: only feat, fix and refactor commits touching web/ move it."
    exit 0
fi

echo "panel: $increment, from the commits since ${last:-the first commit}."
$CZ bump --increment "$increment" --yes "$@"
