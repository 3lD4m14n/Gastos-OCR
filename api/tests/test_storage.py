from collections.abc import Iterator

import pytest

from app.config import get_settings
from app.storage import get_s3_client


@pytest.fixture(autouse=True)
def clean_caches(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x")
    monkeypatch.setenv("S3_BUCKET", "bucket")
    monkeypatch.setenv("AWS_REGION", "us-east-2")
    get_settings.cache_clear()
    get_s3_client.cache_clear()
    yield
    get_settings.cache_clear()
    get_s3_client.cache_clear()


def test_endpoint_local_firma_con_las_claves_de_la_configuracion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("S3_ENDPOINT_URL", "http://localhost:9000")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "clave-local")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secreto-local")

    url = get_s3_client().generate_presigned_url(
        "get_object", Params={"Bucket": "bucket", "Key": "foto.jpg"}
    )

    assert url.startswith("http://localhost:9000/bucket/foto.jpg?")
    assert "clave-local" in url


def test_en_aws_no_usa_las_claves_sueltas_del_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("S3_ENDPOINT_URL", raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "clave-del-rol")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secreto-del-rol")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "token-del-rol")

    url = get_s3_client().generate_presigned_url(
        "get_object", Params={"Bucket": "bucket", "Key": "foto.jpg"}
    )

    # El token solo aparece si boto3 resolvió las credenciales por su cadena normal.
    assert "X-Amz-Security-Token=token-del-rol" in url


def test_el_secreto_no_aparece_al_imprimir_la_configuracion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secreto-local")
    assert "secreto-local" not in repr(get_settings())
