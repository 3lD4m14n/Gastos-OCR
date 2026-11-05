from typing import Any

from aws_cdk import Stack
from constructs import Construct

from infra.cognito import add_auth

DOMAIN_PREFIX = "gastos-ocr-dev"
LOCAL_URL = "http://localhost:5173"


class InfraStack(Stack):
    """Pool de Cognito de desarrollo, usado con Postgres local."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        google_client_id: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        add_auth(
            self,
            domain_prefix=DOMAIN_PREFIX,
            google_client_id=google_client_id,
            app_url=LOCAL_URL,
            protected=False,
        )
