"""Comprueba contra el S3 local el flujo de subida que usará la PWA en la Fase 2.

Requiere el stack levantado. Lee la misma configuración que la API; desde el host:
S3_ENDPOINT_URL=http://localhost:9000.
"""

import sys
import uuid
from collections.abc import Callable

import httpx2 as httpx
from botocore.exceptions import BotoCoreError, ClientError

from app.config import get_settings
from app.storage import get_s3_client

ORIGIN = "http://localhost:5173"
OTHER_ORIGIN = "http://evil.example"
BODY = b"\xff\xd8\xff prueba de humo"


def preflight(url: str, origin: str) -> httpx.Response:
    return httpx.options(
        url,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type",
        },
    )


def run_checks() -> list[tuple[str, bool]]:
    client = get_s3_client()
    bucket = get_settings().s3_bucket
    key = f"smoke/{uuid.uuid4()}.jpg"
    params: dict[str, str] = {"Bucket": bucket, "Key": key, "ContentType": "image/jpeg"}
    put_url = client.generate_presigned_url("put_object", Params=params, ExpiresIn=300)
    get_url = client.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=300
    )
    jpeg = {"Content-Type": "image/jpeg"}
    results: list[tuple[str, bool]] = []

    def check(name: str, condition: Callable[[], bool]) -> None:
        results.append((name, condition()))

    allowed = preflight(put_url, ORIGIN)
    check("preflight CORS permitido", lambda: allowed.is_success)
    check(
        "preflight devuelve el origen",
        lambda: allowed.headers.get("access-control-allow-origin") == ORIGIN,
    )
    denied = preflight(put_url, OTHER_ORIGIN)
    check(
        "preflight rechaza otro origen",
        lambda: denied.headers.get("access-control-allow-origin") not in {OTHER_ORIGIN, "*"},
    )

    tampered = put_url[:-1] + ("0" if put_url[-1] != "0" else "1")
    check(
        "PUT con firma alterada rechazado",
        lambda: httpx.put(tampered, content=BODY, headers=jpeg).status_code == 403,
    )
    check(
        "PUT con otro Content-Type rechazado",
        lambda: (
            httpx.put(put_url, content=BODY, headers={"Content-Type": "text/plain"}).status_code
            == 403
        ),
    )

    try:
        check("PUT prefirmado", lambda: httpx.put(put_url, content=BODY, headers=jpeg).is_success)
        got = httpx.get(get_url)
        check("GET prefirmado devuelve lo subido", lambda: got.is_success and got.content == BODY)
        check(
            "GET sin firma rechazado",
            lambda: httpx.get(get_url.split("?")[0]).status_code == 403,
        )
    finally:
        client.delete_object(Bucket=bucket, Key=key)
    return results


def main() -> int:
    try:
        results = run_checks()
    except (BotoCoreError, ClientError, httpx.HTTPError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    for name, passed in results:
        print(f"{'OK   ' if passed else 'FALLA'} {name}")
    return 0 if all(passed for _, passed in results) else 1


if __name__ == "__main__":
    sys.exit(main())
