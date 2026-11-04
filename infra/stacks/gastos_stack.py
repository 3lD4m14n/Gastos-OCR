from typing import Any

from aws_cdk import Stack
from constructs import Construct


class GastosStack(Stack):
    """Vacío a propósito: los recursos se agregan en la Fase 1."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:
        super().__init__(scope, construct_id, **kwargs)
