"""Valida el access token de Cognito. La API no tiene contraseñas ni sesiones propias."""

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

logger = logging.getLogger(__name__)
bearer = HTTPBearer(auto_error=False)

JWKS_TIMEOUT_SECONDS = 3
# Solo RS256: nunca se acepta el algoritmo que el token declare, ni `none`.
ALGORITHMS = ["RS256"]
REQUIRED_CLAIMS = ["exp", "iss", "sub", "client_id", "token_use"]


class InvalidToken(Exception):
    """El token no es válido."""


class VerifierUnavailable(Exception):
    """No se pudo validar el token: falta configuración o no responde Cognito."""


class TokenVerifier:
    def __init__(self, issuer: str, client_id: str, jwks_client: jwt.PyJWKClient) -> None:
        self._issuer = issuer
        self._client_id = client_id
        self._jwks_client = jwks_client

    def verify(self, token: str) -> str:
        """Devuelve el `sub` del token."""
        try:
            key = self._jwks_client.get_signing_key_from_jwt(token)
        except jwt.PyJWKClientConnectionError as error:
            raise VerifierUnavailable from error
        except (jwt.PyJWKClientError, jwt.InvalidTokenError) as error:
            raise InvalidToken from error

        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                key.key,
                algorithms=ALGORITHMS,
                issuer=self._issuer,
                options={"require": REQUIRED_CLAIMS},
            )
        except jwt.InvalidTokenError as error:
            raise InvalidToken from error

        if claims["token_use"] != "access" or claims["client_id"] != self._client_id:
            raise InvalidToken
        sub = claims["sub"]
        if not isinstance(sub, str) or not sub:
            raise InvalidToken
        return sub


@lru_cache
def get_token_verifier() -> TokenVerifier:
    settings = get_settings()
    if not settings.cognito_user_pool_id or not settings.cognito_client_id:
        raise VerifierUnavailable("Falta COGNITO_USER_POOL_ID o COGNITO_CLIENT_ID")
    issuer = (
        f"https://cognito-idp.{settings.aws_region}.amazonaws.com/{settings.cognito_user_pool_id}"
    )
    jwks = jwt.PyJWKClient(
        f"{issuer}/.well-known/jwks.json", cache_keys=True, timeout=JWKS_TIMEOUT_SECONDS
    )
    return TokenVerifier(issuer, settings.cognito_client_id, jwks)


@dataclass(frozen=True)
class Identity:
    sub: str


def get_identity(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Identity:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail="Sesión inválida o vencida",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        return Identity(sub=get_token_verifier().verify(credentials.credentials))
    except InvalidToken as error:
        raise unauthorized from error
    except VerifierUnavailable as error:
        logger.exception("No se pudo validar el token")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo validar la sesión; probá de nuevo en unos minutos",
        ) from error
