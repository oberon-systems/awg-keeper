#!/bin/sh
# eslint and tsc over the interface, when this machine can run them.
#
# node is not a dependency of the panel itself - the image builds the interface
# in a stage of its own - so a checkout without node_modules says so and stops
# rather than failing a push for a toolchain it was never asked to install.
set -eu

UI_DIR=$(cd "$(dirname "$0")/../ui" && pwd)
cd "$UI_DIR"

if ! command -v npm >/dev/null 2>&1; then
    echo "ui: npm is not installed; skipping eslint and tsc."
    exit 0
fi

if [ ! -d node_modules ]; then
    echo "ui: node_modules is absent; run 'make -C web ui' to check the ui."
    exit 0
fi

npm run lint
npm run typecheck
