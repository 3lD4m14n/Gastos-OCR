"""Trigger de Cognito: solo pueden crearse cuentas con un email de la lista."""

import os
from typing import Any


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    allowed = {
        email.strip().casefold()
        for email in os.environ.get("ALLOWED_EMAILS", "").split(",")
        if email.strip()
    }
    email = event["request"]["userAttributes"].get("email", "").strip().casefold()
    # Con la lista vacía o sin email no entra nadie. El email no se registra en los logs.
    if email not in allowed:
        raise PermissionError("Esta cuenta no tiene acceso")
    return event
