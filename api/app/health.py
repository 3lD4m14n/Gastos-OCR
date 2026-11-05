import logging
from typing import Literal

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.db import get_engine
from app.storage import get_s3_client

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])

CheckStatus = Literal["ok", "error"]


class Liveness(BaseModel):
    status: Literal["ok"] = "ok"


class Readiness(BaseModel):
    status: Literal["ok", "unavailable"]
    checks: dict[str, CheckStatus]


def check_database() -> CheckStatus:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Falló el chequeo de Postgres")
        return "error"
    return "ok"


def check_storage() -> CheckStatus:
    try:
        get_s3_client().head_bucket(Bucket=get_settings().s3_bucket)
    except BotoCoreError, ClientError:
        logger.exception("Falló el chequeo de S3")
        return "error"
    return "ok"


def readiness_checks() -> dict[str, CheckStatus]:
    return {"database": check_database(), "storage": check_storage()}


@router.get("/health")
def health() -> Liveness:
    """Indica que el proceso responde; no toca dependencias."""
    return Liveness()


@router.get("/health/ready")
def ready(
    response: Response,
    checks: dict[str, CheckStatus] = Depends(readiness_checks),  # noqa: B008
) -> Readiness:
    """Comprueba Postgres y S3. El detalle de los errores queda solo en los logs."""
    if all(result == "ok" for result in checks.values()):
        return Readiness(status="ok", checks=checks)
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return Readiness(status="unavailable", checks=checks)
