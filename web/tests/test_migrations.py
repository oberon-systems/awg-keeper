"""The migration and the models must describe the same schema.

Running alembic here would only prove alembic runs. What actually rots is the
migration falling behind a model nobody remembered to migrate.
"""

from __future__ import annotations

import re
from pathlib import Path

from sqlmodel import SQLModel

from awg_panel import models  # noqa: F401

INITIAL = Path(__file__).resolve().parents[1] / "migrations/versions/0001_initial.py"
CREATED = r'op\.create_table\(\n\s+"([a-z_]+)"'


def test_every_model_table_is_created_by_the_migration() -> None:
    created = set(re.findall(CREATED, INITIAL.read_text()))
    assert set(SQLModel.metadata.tables) == created


def test_the_migration_drops_what_it_creates() -> None:
    text = INITIAL.read_text()
    created = set(re.findall(CREATED, text))
    dropped = set(re.findall(r'op\.drop_table\("([a-z_]+)"\)', text))
    assert created == dropped
