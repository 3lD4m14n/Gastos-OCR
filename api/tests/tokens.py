"""Tokens con la misma forma que los de Cognito, firmados con una clave RSA de prueba."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

ISSUER = "https://cognito-idp.us-east-2.amazonaws.com/us-east-2_prueba"
PRIVATE_KEY: RSAPrivateKey = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY: RSAPrivateKey = rsa.generate_private_key(public_exponent=65537, key_size=2048)


@dataclass
class _SigningKey:
    key: RSAPublicKey


class StubJwksClient:
    """Reemplaza la descarga del JWKS."""

    def __init__(self) -> None:
        self.error: Exception | None = None

    def get_signing_key_from_jwt(self, _token: str) -> _SigningKey:
        if self.error is not None:
            raise self.error
        return _SigningKey(PRIVATE_KEY.public_key())


def claims(sub: str = "usuario-a", **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "sub": sub,
        "iss": ISSUER,
        "client_id": "cliente-de-prueba",
        "token_use": "access",
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    base.update(overrides)
    return {key: value for key, value in base.items() if value is not None}


def access_token(sub: str = "usuario-a", key: RSAPrivateKey = PRIVATE_KEY, **overrides: Any) -> str:
    return jwt.encode(claims(sub, **overrides), key, algorithm="RS256")
