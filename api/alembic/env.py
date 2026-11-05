"""Corre las migraciones. Las URL y los tokens salen de la configuración de la app.

Autocommit en los dos motores: DSQL admite una sola sentencia DDL por transacción y no la mezcla
con cambios de datos. Así Postgres local se comporta igual, y un error de ese tipo aparece antes.
"""

from sqlalchemy import create_engine

from alembic import context
from app.config import get_settings
from app.db import ADMIN_ROLE, create_dsql_engine
from app.models import Base


def run() -> None:
    settings = get_settings()
    if settings.dsql_endpoint:
        engine = create_dsql_engine(settings, ADMIN_ROLE, isolation_level="AUTOCOMMIT")
    elif settings.database_url:
        engine = create_engine(settings.database_url, isolation_level="AUTOCOMMIT")
    else:
        raise ValueError("Falta DATABASE_URL o DSQL_ENDPOINT")

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            transactional_ddl=False,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("El modo offline no está soportado")
run()
