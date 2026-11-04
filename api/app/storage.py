from functools import lru_cache
from typing import TYPE_CHECKING

import boto3
from botocore.config import Config

from app.config import get_settings

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


@lru_cache
def get_s3_client() -> S3Client:
    settings = get_settings()
    # Con endpoint local se firma solo con las claves locales, nunca con credenciales reales.
    # En AWS van en None para que boto3 use el rol de IAM: Lambda define AWS_ACCESS_KEY_ID,
    # pero esa clave no sirve sin el token de sesión que la acompaña.
    local = settings.s3_endpoint_url is not None
    secret = settings.aws_secret_access_key
    return boto3.client(
        "s3",
        region_name=settings.aws_region,
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.aws_access_key_id if local else None,
        aws_secret_access_key=secret.get_secret_value() if local and secret else None,
        config=Config(
            signature_version="s3v4",
            # El estilo de ruta evita depender de DNS con subdominios por bucket en local.
            s3={"addressing_style": "path" if local else "auto"},
            connect_timeout=2,
            read_timeout=5,
            retries={"total_max_attempts": 2, "mode": "standard"},
        ),
    )
