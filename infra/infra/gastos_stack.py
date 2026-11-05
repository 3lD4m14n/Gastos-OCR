from pathlib import Path
from typing import Any

from aws_cdk import CfnOutput, CfnParameter, Duration, RemovalPolicy, Stack, triggers
from aws_cdk import aws_amplify as amplify
from aws_cdk import aws_budgets as budgets
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dsql as dsql
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from constructs import Construct

from infra.cognito import add_auth

API_DIR = Path(__file__).resolve().parents[2] / "api"
PRE_SIGNUP_DIR = Path(__file__).resolve().parents[1] / "lambdas" / "pre_signup"
DOMAIN_PREFIX = "gastos-ocr-prod"
BRANCH = "main"
MONTHLY_BUDGET_USD = 20
# Acota el gasto ante abuso: la Function URL es pública y la autenticación la hace FastAPI.
API_RESERVED_CONCURRENCY = 10


class GastosStack(Stack):
    """Entorno de producción: DSQL, API en Lambda, web en Amplify y Cognito propio."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        google_client_id: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # El email no se versiona: el repositorio es público.
        budget_email = CfnParameter(
            self,
            "BudgetEmail",
            type="String",
            no_echo=True,
            allowed_pattern=r"[^@\s]+@[^@\s]+\.[^@\s]+",
            description="Destinatario de las alertas de presupuesto",
        )

        # Tampoco se versiona: quién puede entrar se decide al desplegar.
        allowed_emails = CfnParameter(
            self,
            "AllowedEmails",
            type="String",
            no_echo=True,
            allowed_pattern=r"[^@\s,]+@[^@\s,]+\.[^@\s,]+(,[^@\s,]+@[^@\s,]+\.[^@\s,]+)*",
            description="Emails que pueden crear una cuenta, separados por comas",
        )

        # Conserva los datos también si falla el primer deploy y CloudFormation hace rollback.
        cluster = dsql.CfnCluster(self, "Database", deletion_protection_enabled=True)
        cluster.apply_removal_policy(RemovalPolicy.RETAIN)

        bucket = s3.Bucket(
            self,
            "Tickets",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        web = self._add_web()
        branch_domain = f"{BRANCH}.{web.attr_default_domain}"
        web_url = f"https://{branch_domain}"

        auth = add_auth(
            self,
            domain_prefix=DOMAIN_PREFIX,
            google_client_id=google_client_id,
            app_url=web_url,
            protected=True,
        )

        # Corre solo la primera vez que entra una cuenta, incluidas las de Google.
        pre_signup = lambda_.Function(
            self,
            "PreSignUp",
            runtime=lambda_.Runtime.PYTHON_3_14,
            handler="index.handler",
            code=lambda_.Code.from_asset(str(PRE_SIGNUP_DIR), exclude=["__pycache__"]),
            timeout=Duration.seconds(5),
            log_group=self._log_group("PreSignUpLogs"),
            environment={"ALLOWED_EMAILS": allowed_emails.value_as_string},
        )
        auth.user_pool.add_trigger(cognito.UserPoolOperation.PRE_SIGN_UP, pre_signup)

        shared_env = {
            "DSQL_ENDPOINT": cluster.attr_endpoint,
            "S3_BUCKET": bucket.bucket_name,
        }

        # El rol existe antes que la función: las migraciones lo asocian al rol de base de datos.
        api_role = iam.Role(
            self,
            "ApiRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )
        # Sin DbConnectAdmin: la API solo se conecta con el rol de base sin privilegios.
        api_role.add_to_policy(
            iam.PolicyStatement(actions=["dsql:DbConnect"], resources=[cluster.attr_resource_arn])
        )
        # Solo lo que usa `/health/ready`. Leer y escribir objetos entra con el OCR, en la Fase 2.
        api_role.add_to_policy(
            iam.PolicyStatement(actions=["s3:ListBucket"], resources=[bucket.bucket_arn])
        )

        migrate = lambda_.DockerImageFunction(
            self,
            "Migrate",
            code=self._image("lambda-task"),
            architecture=lambda_.Architecture.X86_64,
            memory_size=512,
            # Los índices de DSQL se construyen de forma asíncrona y la migración los espera.
            timeout=Duration.minutes(10),
            log_group=self._log_group("MigrateLogs"),
            environment={**shared_env, "API_ROLE_ARN": api_role.role_arn},
        )
        migrate.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dsql:DbConnectAdmin"], resources=[cluster.attr_resource_arn]
            )
        )

        api = lambda_.DockerImageFunction(
            self,
            "Api",
            code=self._image("lambda-api"),
            architecture=lambda_.Architecture.X86_64,
            role=api_role,
            # También duplica la CPU: con 512 MB, el arranque superaba los 10 s de init de Lambda.
            memory_size=1024,
            timeout=Duration.seconds(29),
            reserved_concurrent_executions=API_RESERVED_CONCURRENCY,
            log_group=self._log_group("ApiLogs"),
            environment={
                **shared_env,
                "CORS_ALLOWED_ORIGINS": web_url,
                "COGNITO_USER_POOL_ID": auth.user_pool.user_pool_id,
                "COGNITO_CLIENT_ID": auth.client.user_pool_client_id,
            },
        )
        # CORS lo resuelve FastAPI; configurarlo también acá duplicaría los encabezados.
        api_url = api.add_function_url(auth_type=lambda_.FunctionUrlAuthType.NONE)

        # Si una migración falla, el deploy falla antes de actualizar la API.
        triggers.Trigger(
            self,
            "RunMigrations",
            handler=migrate,
            timeout=Duration.minutes(10),
            invocation_type=triggers.InvocationType.REQUEST_RESPONSE,
            execute_after=[cluster],
            execute_before=[api],
        )

        budgets.CfnBudget(
            self,
            "MonthlyBudget",
            budget=budgets.CfnBudget.BudgetDataProperty(
                budget_type="COST",
                time_unit="MONTHLY",
                budget_limit=budgets.CfnBudget.SpendProperty(amount=MONTHLY_BUDGET_USD, unit="USD"),
                # Con los créditos incluidos, el gasto daría 0 y la alerta nunca saltaría.
                cost_types=budgets.CfnBudget.CostTypesProperty(
                    include_credit=False, include_refund=False
                ),
            ),
            notifications_with_subscribers=[
                self._budget_alert("ACTUAL", 80, budget_email.value_as_string),
                self._budget_alert("FORECASTED", 100, budget_email.value_as_string),
            ],
        )

        CfnOutput(self, "ApiUrl", value=api_url.url)
        CfnOutput(self, "WebUrl", value=web_url)
        CfnOutput(self, "AmplifyAppId", value=web.attr_app_id)
        CfnOutput(self, "AmplifyBranch", value=BRANCH)
        CfnOutput(self, "DsqlEndpoint", value=cluster.attr_endpoint)
        CfnOutput(
            self,
            "GoogleRedirectUri",
            value=f"{auth.domain.base_url()}/oauth2/idpresponse",
        )

    def _add_web(self) -> amplify.CfnApp:
        login_host = f"{DOMAIN_PREFIX}.auth.{self.region}.amazoncognito.com"
        issuer_host = f"cognito-idp.{self.region}.amazonaws.com"
        # La URL de la API aún no se conoce: depende de esta app por CORS. El comodín se acota
        # en el build con un <meta> CSP que nombra el origen exacto (ver web/vite.config.ts).
        csp = "; ".join(
            [
                "default-src 'self'",
                "script-src 'self'",
                # Base UI y Recharts usan atributos `style`.
                "style-src 'self' 'unsafe-inline'",
                "img-src 'self' data:",
                "font-src 'self'",
                "connect-src 'self' "
                f"https://*.lambda-url.{self.region}.on.aws "
                f"https://{issuer_host} https://{login_host}",
                "worker-src 'self'",
                "manifest-src 'self'",
                "object-src 'none'",
                "base-uri 'self'",
                "form-action 'self'",
                "frame-ancestors 'none'",
            ]
        )
        custom_headers = f"""customHeaders:
  - pattern: '**'
    headers:
      - key: Content-Security-Policy
        value: "{csp}"
      - key: Strict-Transport-Security
        value: max-age=31536000; includeSubDomains
      - key: X-Content-Type-Options
        value: nosniff
      - key: Referrer-Policy
        value: strict-origin-when-cross-origin
"""
        app = amplify.CfnApp(
            self,
            "Web",
            name="gastos-ocr",
            platform="WEB",
            custom_headers=custom_headers,
            custom_rules=[
                # Las rutas de la SPA sirven index.html; los archivos con extensión, no.
                amplify.CfnApp.CustomRuleProperty(
                    source=(
                        r"</^[^.]+$|\.(?!(css|gif|ico|jpg|js|png|txt|svg|woff|woff2|ttf|map"
                        r"|json|webmanifest|webp)$)([^.]+$)/>"
                    ),
                    target="/index.html",
                    status="200",
                )
            ],
        )
        amplify.CfnBranch(
            self,
            "WebBranch",
            app_id=app.attr_app_id,
            branch_name=BRANCH,
            stage="PRODUCTION",
            # Se publica con infra/scripts/deploy_web.sh; el deploy desde CI queda para la Fase 3.
            enable_auto_build=False,
        )
        return app

    def _image(self, target: str) -> lambda_.DockerImageCode:
        return lambda_.DockerImageCode.from_image_asset(
            str(API_DIR),
            target=target,
            platform=ecr_assets.Platform.LINUX_AMD64,
        )

    def _log_group(self, construct_id: str) -> logs.LogGroup:
        return logs.LogGroup(
            self,
            construct_id,
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )

    @staticmethod
    def _budget_alert(
        notification_type: str, threshold: int, email: str
    ) -> budgets.CfnBudget.NotificationWithSubscribersProperty:
        return budgets.CfnBudget.NotificationWithSubscribersProperty(
            notification=budgets.CfnBudget.NotificationProperty(
                notification_type=notification_type,
                comparison_operator="GREATER_THAN",
                threshold=threshold,
                threshold_type="PERCENTAGE",
            ),
            subscribers=[
                budgets.CfnBudget.SubscriberProperty(subscription_type="EMAIL", address=email)
            ],
        )
