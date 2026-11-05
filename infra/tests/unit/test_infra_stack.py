import json

import aws_cdk as core
import aws_cdk.assertions as assertions
import pytest
from aws_cdk.assertions import Match

from infra.infra_stack import GOOGLE_SECRET_NAME, InfraStack


@pytest.fixture
def template() -> assertions.Template:
    stack = InfraStack(core.App(), "infra", google_client_id="cliente.apps.googleusercontent.com")
    return assertions.Template.from_stack(stack)


def test_pool_essentials_sin_registro_abierto(template: assertions.Template) -> None:
    template.has_resource_properties(
        "AWS::Cognito::UserPool",
        {
            "UserPoolTier": "ESSENTIALS",
            "AdminCreateUserConfig": {"AllowAdminCreateUserOnly": True},
        },
    )


def test_cliente_publico_solo_con_authorization_code(template: assertions.Template) -> None:
    template.has_resource_properties(
        "AWS::Cognito::UserPoolClient",
        {
            "GenerateSecret": False,
            "AllowedOAuthFlows": ["code"],
            "AllowedOAuthFlowsUserPoolClient": True,
            "CallbackURLs": ["http://localhost:5173"],
            "SupportedIdentityProviders": Match.array_with(["COGNITO", "Google"]),
        },
    )


def test_sesion_de_30_dias_con_rotacion(template: assertions.Template) -> None:
    template.has_resource_properties(
        "AWS::Cognito::UserPoolClient",
        {
            "RefreshTokenValidity": 43200,
            "TokenValidityUnits": Match.object_like({"RefreshToken": "minutes"}),
            "RefreshTokenRotation": {"Feature": "ENABLED", "RetryGracePeriodSeconds": 10},
            # Sin valor explícito, Cognito activa ALLOW_REFRESH_TOKEN_AUTH.
            "ExplicitAuthFlows": ["ALLOW_USER_SRP_AUTH"],
            "EnableTokenRevocation": True,
        },
    )


def test_login_administrado_con_branding(template: assertions.Template) -> None:
    template.has_resource_properties(
        "AWS::Cognito::UserPoolDomain",
        {"Domain": "gastos-ocr-dev", "ManagedLoginVersion": 2},
    )
    template.has_resource_properties(
        "AWS::Cognito::ManagedLoginBranding",
        {"UseCognitoProvidedValues": True},
    )


def test_secreto_de_google_es_una_referencia(template: assertions.Template) -> None:
    resources = template.find_resources("AWS::Cognito::UserPoolIdentityProvider")
    (provider,) = resources.values()
    details = provider["Properties"]["ProviderDetails"]
    assert f"resolve:secretsmanager:{GOOGLE_SECRET_NAME}" in json.dumps(details)
