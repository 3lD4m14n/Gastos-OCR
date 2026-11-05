"""Ayudas para migraciones que deben funcionar en Postgres y en Aurora DSQL."""

from sqlalchemy import text

from alembic import op
from app.config import get_settings


def create_index(
    name: str,
    table: str,
    columns: list[str],
    *,
    unique: bool = False,
    where: str | None = None,
) -> None:
    """Crea un índice y espera a que esté listo.

    DSQL exige `CREATE INDEX ASYNC`, sintaxis que Postgres no acepta. Un índice ASYNC no valida
    nada hasta terminar de construirse, por eso se espera al trabajo.
    """
    is_dsql = bool(get_settings().dsql_endpoint)
    statement = (
        f"CREATE {'UNIQUE ' if unique else ''}INDEX {'ASYNC ' if is_dsql else ''}{name} "
        f"ON {table} ({', '.join(columns)})"
    )
    if where:
        statement += f" WHERE {where}"
    connection = op.get_bind()
    result = connection.execute(text(statement))
    if is_dsql:
        job_id = result.scalar_one()
        connection.execute(text("CALL sys.wait_for_job(:job_id)"), {"job_id": job_id})
