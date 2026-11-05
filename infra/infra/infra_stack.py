from typing import Any

from aws_cdk import CfnOutput, Duration, RemovalPolicy, SecretValue, Stack
from aws_cdk import aws_cognito as cognito
from constructs import Construct

DOMAIN_PREFIX = "gastos-ocr-dev"
GOOGLE_SECRET_NAME = "gastos-ocr/dev/google-client-secret"
LOCAL_URL = "http://localhost:5173"


class InfraStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        google_client_id: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name=DOMAIN_PREFIX,
            feature_plan=cognito.FeaturePlan.ESSENTIALS,
            # Solo entran cuentas de Google o usuarios creados con admin-create-user.
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True),
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=12,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=False,
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            # Pool de desarrollo: se borra con el stack. Prod debe conservarlo,
            # porque el `sub` de cada usuario es la llave de todos sus datos.
            removal_policy=RemovalPolicy.DESTROY,
            deletion_protection=False,
        )

        google = cognito.UserPoolIdentityProviderGoogle(
            self,
            "Google",
            user_pool=user_pool,
            client_id=google_client_id,
            client_secret_value=SecretValue.secrets_manager(GOOGLE_SECRET_NAME),
            scopes=["openid", "email", "profile"],
            attribute_mapping=cognito.AttributeMapping(
                email=cognito.ProviderAttribute.GOOGLE_EMAIL,
                fullname=cognito.ProviderAttribute.GOOGLE_NAME,
            ),
        )

        client = user_pool.add_client(
            "WebClient",
            user_pool_client_name="web",
            # Cliente público: un secreto en el navegador no sería secreto.
            generate_secret=False,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(authorization_code_grant=True),
                scopes=[
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.PROFILE,
                ],
                callback_urls=[LOCAL_URL],
                logout_urls=[LOCAL_URL],
            ),
            supported_identity_providers=[
                cognito.UserPoolClientIdentityProvider.COGNITO,
                cognito.UserPoolClientIdentityProvider.GOOGLE,
            ],
            access_token_validity=Duration.hours(1),
            id_token_validity=Duration.hours(1),
            refresh_token_validity=Duration.days(30),
            refresh_token_rotation_grace_period=Duration.seconds(10),
            enable_token_revocation=True,
            prevent_user_existence_errors=True,
        )
        # Sin valor explícito, Cognito activa ALLOW_REFRESH_TOKEN_AUTH, incompatible con la
        # rotación. El login administrado renueva por /oauth2/token, que sí la admite.
        cfn_client = client.node.default_child
        assert isinstance(cfn_client, cognito.CfnUserPoolClient)
        cfn_client.explicit_auth_flows = ["ALLOW_USER_SRP_AUTH"]

        # El cliente no puede declarar Google hasta que el proveedor exista.
        client.node.add_dependency(google)

        domain = user_pool.add_domain(
            "Domain",
            cognito_domain=cognito.CognitoDomainOptions(domain_prefix=DOMAIN_PREFIX),
            managed_login_version=cognito.ManagedLoginVersion.NEWER_MANAGED_LOGIN,
        )

        # Sin un estilo por cliente, el login administrado queda inutilizable.
        branding = cognito.CfnManagedLoginBranding(
            self,
            "WebClientBranding",
            user_pool_id=user_pool.user_pool_id,
            client_id=client.user_pool_client_id,
            use_cognito_provided_values=True,
        )
        branding.node.add_dependency(domain)

        CfnOutput(self, "UserPoolId", value=user_pool.user_pool_id)
        CfnOutput(self, "WebClientId", value=client.user_pool_client_id)
        CfnOutput(self, "Issuer", value=user_pool.user_pool_provider_url)
        CfnOutput(self, "LoginDomain", value=domain.base_url())
