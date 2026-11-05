"""Guardas para migraciones: el CI usa Postgres y no detecta los límites de Aurora DSQL."""

import re
from pathlib import Path

import pytest
from sqlalchemy import Engine

from alembic import command
from app.migrate import API_ROOT, alembic_config

VERSIONS = sorted((API_ROOT / "alembic" / "versions").glob("*.py"))
FORBIDDEN = {
    r"\bop\.create_index\b": "usá app.migrations.create_index: DSQL exige CREATE INDEX ASYNC",
    r"\bop\.bulk_insert\b": "DSQL no mezcla DDL con datos en una transacción; andá en otra",
    r"\bsa\.Enum\b": "DSQL no admite CREATE TYPE",
    r"\bSERIAL\b|\bautoincrement\b": "usá UUID generados por la aplicación",
    r"\bop\.create_foreign_key\b": "declará las claves foráneas al crear la tabla",
    r"\bop\.alter_column\b": "DSQL limita ALTER TABLE; revisalo contra su documentación",
    r"\bTRUNCATE\b": "DSQL no admite TRUNCATE",
}


def test_hay_migraciones() -> None:
    assert VERSIONS


@pytest.mark.parametrize("path", VERSIONS, ids=lambda p: p.name)
def test_migracion_compatible_con_dsql(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    for pattern, reason in FORBIDDEN.items():
        assert not re.search(pattern, source), f"{path.name}: {reason}"
    for statement in re.findall(r"op\.execute\(\s*[\"'](.+?)[\"']", source, re.DOTALL):
        assert ";" not in statement, f"{path.name}: una sentencia por op.execute"


def test_los_modelos_coinciden_con_las_migraciones(migrated_engine: Engine) -> None:
    command.check(alembic_config())
