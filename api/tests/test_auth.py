import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from fastapi.testclient import TestClient

from app import auth
from app.auth import InvalidToken, TokenVerifier, VerifierUnavailable
from app.main import app
from tests.tokens import OTHER_KEY, PRIVATE_KEY, access_token, claims


def test_token_valido_devuelve_el_sub(verifier: TokenVerifier) -> None:
    assert verifier.verify(access_token(sub="abc")) == "abc"


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"iss": "https://otro.example.com/pool"}, id="otro-emisor"),
        pytest.param({"client_id": "otra-app"}, id="otro-cliente"),
        pytest.param({"token_use": "id"}, id="id-token"),
        pytest.param({"exp": datetime.now(UTC) - timedelta(minutes=1)}, id="vencido"),
        pytest.param({"exp": None}, id="sin-exp"),
        pytest.param({"client_id": None}, id="sin-client-id"),
        pytest.param({"token_use": None}, id="sin-token-use"),
        pytest.param({"sub": ""}, id="sub-vacio"),
    ],
)
def test_rechaza_claims_invalidos(verifier: TokenVerifier, overrides: dict[str, Any]) -> None:
    with pytest.raises(InvalidToken):
        verifier.verify(access_token(**overrides))


def test_rechaza_firma_de_otra_clave(verifier: TokenVerifier) -> None:
    with pytest.raises(InvalidToken):
        verifier.verify(access_token(key=OTHER_KEY))


def test_rechaza_alg_none(verifier: TokenVerifier) -> None:
    def part(value: dict[str, Any]) -> str:
        raw = json.dumps(value, default=lambda d: int(d.timestamp())).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    token = f"{part({'alg': 'none', 'typ': 'JWT'})}.{part(claims())}."
    with pytest.raises(InvalidToken):
        verifier.verify(token)


def test_rechaza_hs256_firmado_con_la_clave_publica(verifier: TokenVerifier) -> None:
    """El ataque clásico: usar la clave pública, que es conocida, como secreto de HMAC."""

    def part(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    public_pem = PRIVATE_KEY.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    payload = json.dumps(claims(), default=lambda d: int(d.timestamp())).encode()
    signed = f"{part(b'{"alg":"HS256","typ":"JWT"}')}.{part(payload)}"
    signature = hmac.new(public_pem, signed.encode(), hashlib.sha256).digest()
    with pytest.raises(InvalidToken):
        verifier.verify(f"{signed}.{part(signature)}")


def test_clave_desconocida_es_token_invalido(verifier: TokenVerifier) -> None:
    verifier._jwks_client.error = jwt.PyJWKClientError("kid desconocido")  # type: ignore[attr-defined]
    with pytest.raises(InvalidToken):
        verifier.verify(access_token())


def test_jwks_caido_no_se_confunde_con_token_invalido(verifier: TokenVerifier) -> None:
    verifier._jwks_client.error = jwt.PyJWKClientConnectionError("sin red")  # type: ignore[attr-defined]
    with pytest.raises(VerifierUnavailable):
        verifier.verify(access_token())


def test_endpoint_sin_token_responde_401(verifier: TokenVerifier) -> None:
    response = TestClient(app).get("/api/v1/users/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_endpoint_con_token_invalido_responde_401(verifier: TokenVerifier) -> None:
    headers = {"Authorization": f"Bearer {access_token(token_use='id')}"}
    assert TestClient(app).get("/api/v1/users/me", headers=headers).status_code == 401


def test_endpoint_con_jwks_caido_responde_503(verifier: TokenVerifier) -> None:
    verifier._jwks_client.error = jwt.PyJWKClientConnectionError("sin red")  # type: ignore[attr-defined]
    headers = {"Authorization": f"Bearer {access_token()}"}
    assert TestClient(app).get("/api/v1/users/me", headers=headers).status_code == 503


def test_sin_configuracion_de_cognito_responde_503(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable() -> TokenVerifier:
        raise VerifierUnavailable

    monkeypatch.setattr(auth, "get_token_verifier", unavailable)
    headers = {"Authorization": f"Bearer {access_token()}"}
    assert TestClient(app).get("/api/v1/users/me", headers=headers).status_code == 503
