"""Conexión a la base y transacciones con reintento.

Aurora DSQL no bloquea: si dos transacciones chocan, una falla al confirmar con el error 40001 y
hay que repetirla. En Postgres ese error es raro, pero el mismo camino también lo cubre.
"""

import random
import time
from collections.abc import Callable
from functools import lru_cache
from typing import Any

import boto3
from sqlalchemy import URL, Engine, create_engine, event
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings

SERIALIZATION_FAILURE = "40001"
MAX_ATTEMPTS = 4
# Sin esto, el dialecto de psycopg consulta hstore dentro de un SAVEPOINT, que DSQL no admite.
DSQL_DIALECT_OPTIONS: dict[str, Any] = {"use_native_hstore": False}
# DSQL cierra las conexiones a la hora; se renuevan antes.
DSQL_POOL_RECYCLE_SECONDS = 3000
ADMIN_ROLE = "admin"


def create_dsql_engine(settings: Settings, role: str, **options: Any) -> Engine:
    endpoint = settings.dsql_endpoint
    if not endpoint:
        raise ValueError("Falta DSQL_ENDPOINT")
    url = URL.create(
        "postgresql+psycopg",
        username=role,
        host=endpoint,
        database="postgres",
        query={"sslmode": "require"},
    )
    engine = create_engine(url, **DSQL_DIALECT_OPTIONS, **options)
    # Los generadores de tokens se agregan al cliente en ejecución: los stubs no los conocen.
    client: Any = boto3.client("dsql", region_name=settings.aws_region)

    @event.listens_for(engine, "do_connect")
    def provide_token(
        _dialect: Any, _record: Any, _args: Any, connect_params: dict[str, Any]
    ) -> None:
        # El token dura poco y se firma en local: se genera uno por cada conexión nueva.
        generate = (
            client.generate_db_connect_admin_auth_token
            if role == ADMIN_ROLE
            else client.generate_db_connect_auth_token
        )
        connect_params["password"] = generate(Hostname=endpoint, Region=settings.aws_region)

    return engine


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    # Pool mínimo: Lambda atiende una petición por vez en cada entorno.
    options: dict[str, Any] = {
        "pool_pre_ping": True,
        "pool_size": 1,
        "max_overflow": 1,
        "connect_args": {"connect_timeout": 5},
    }
    if settings.dsql_endpoint:
        return create_dsql_engine(
            settings, settings.dsql_role, pool_recycle=DSQL_POOL_RECYCLE_SECONDS, **options
        )
    if not settings.database_url:
        raise ValueError("Falta DATABASE_URL")
    return create_engine(settings.database_url, **options)


def is_serialization_failure(error: DBAPIError) -> bool:
    return getattr(error.orig, "sqlstate", None) == SERIALIZATION_FAILURE


def run_transaction[T](work: Callable[[Session], T], *, engine: Engine | None = None) -> T:
    """Ejecuta `work` en una transacción y la repite completa si hay un conflicto.

    `work` no debe tener efectos fuera de la base, porque puede ejecutarse más de una vez.
    """
    target = engine if engine is not None else get_engine()
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with Session(target, expire_on_commit=False) as session, session.begin():
                return work(session)
        except DBAPIError as error:
            if attempt == MAX_ATTEMPTS or not is_serialization_failure(error):
                raise
            time.sleep(random.uniform(0, 0.05 * 2**attempt))
    raise AssertionError("El bucle siempre retorna o relanza el error")
