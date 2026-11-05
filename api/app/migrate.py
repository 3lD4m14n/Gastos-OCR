"""Aplica las migraciones durante el deploy y deja listo el rol de la API en Aurora DSQL."""

import re
from pathlib import Path
from typing import Any

from alembic.config import Config
from sqlalchemy import text

from alembic import command
from app.config import Settings, get_settings
from app.db import ADMIN_ROLE, create_dsql_engine
from app.models import Base

API_ROOT = Path(__file__).resolve().parents[1]
IAM_ROLE_ARN = re.compile(r"^arn:aws:iam::\d{12}:role/[\w+=,.@/-]+$")
ROLE_NAME = re.compile(r"^[a-z_][a-z0-9_]*$")


def alembic_config() -> Config:
    config = Config(API_ROOT / "alembic.ini")
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    return config


def grant_api_role(settings: Settings, iam_role_arn: str) -> None:
    """Crea el rol sin privilegios de administrador y lo asocia al rol de IAM de la API.

    Solo recibe permisos de datos sobre las tablas de la app: no puede cambiar el esquema.
    """
    role = settings.dsql_role
    # Estos valores no admiten parámetros en SQL y salen de la configuración del deploy.
    if not ROLE_NAME.fullmatch(role) or not IAM_ROLE_ARN.fullmatch(iam_role_arn):
        raise ValueError("Rol de base de datos o ARN de IAM inválido")

    engine = create_dsql_engine(settings, ADMIN_ROLE, isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        exists = connection.scalar(
            text("SELECT 1 FROM pg_roles WHERE rolname = :role"), {"role": role}
        )
        if not exists:
            connection.execute(text(f"CREATE ROLE {role} WITH LOGIN"))
        mapped = connection.scalar(
            text(
                "SELECT 1 FROM sys.iam_pg_role_mappings WHERE pg_role_name = :role AND arn = :arn"
            ),
            {"role": role, "arn": iam_role_arn},
        )
        if not mapped:
            connection.execute(text(f"AWS IAM GRANT {role} TO '{iam_role_arn}'"))
        tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
        connection.execute(text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {tables} TO {role}"))
    engine.dispose()


def handler(event: dict[str, Any], _context: Any) -> dict[str, str]:
    command.upgrade(alembic_config(), "head")
    settings = get_settings()
    if settings.dsql_endpoint:
        grant_api_role(settings, event.get("api_role_arn") or settings.api_role_arn)
    return {"status": "ok"}
