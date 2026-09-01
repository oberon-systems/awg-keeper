#!/bin/sh
# Migrations first, always. The schema a container starts on is the schema its
# code was written against, and alembic is what makes that true after an
# upgrade as well as on a first run.
set -eu

alembic upgrade head
exec python -m awg_panel
