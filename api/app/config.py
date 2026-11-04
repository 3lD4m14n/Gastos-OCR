from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    s3_bucket: str
    # Solo en local: apunta a RustFS. En AWS queda vacío y se usa S3.
    s3_endpoint_url: str | None = None
    # Solo para el S3 local. En AWS quedan vacías y boto3 usa el rol de IAM.
    aws_access_key_id: str | None = None
    aws_secret_access_key: SecretStr | None = None
    aws_region: str
    cors_allowed_origins: str = "http://localhost:5173"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
