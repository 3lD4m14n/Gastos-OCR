from functools import lru_cache
from typing import Self

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # En local: Postgres por URL. En AWS: Aurora DSQL con token IAM, sin contraseña.
    database_url: str | None = None
    dsql_endpoint: str | None = None
    dsql_role: str = "gastos_api"
    # Rol de IAM de la API; solo lo usan las migraciones en AWS.
    api_role_arn: str = ""
    s3_bucket: str
    # Solo en local: apunta a RustFS. En AWS queda vacío y se usa S3.
    s3_endpoint_url: str | None = None
    # Solo para el S3 local. En AWS quedan vacías y boto3 usa el rol de IAM.
    aws_access_key_id: str | None = None
    aws_secret_access_key: SecretStr | None = None
    aws_region: str
    cors_allowed_origins: str = "http://localhost:5173"
    # Vacíos, la API arranca pero rechaza con 503 toda ruta que requiera autenticación.
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""

    @model_validator(mode="after")
    def requires_a_database(self) -> Self:
        if not self.database_url and not self.dsql_endpoint:
            raise ValueError("Falta DATABASE_URL o DSQL_ENDPOINT")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
