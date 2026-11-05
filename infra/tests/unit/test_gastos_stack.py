import json

import aws_cdk as core
import aws_cdk.assertions as assertions
import pytest
from aws_cdk.assertions import Match

from infra.gastos_stack import GastosStack


@pytest.fixture(scope="module")
def template() -> assertions.Template:
    stack = GastosStack(
        core.App(),
        "prod",
        env=core.Environment(region="us-east-2"),
        google_client_id="cliente.apps.googleusercontent.com",
    )
    return assertions.Template.from_stack(stack)


def _role_policies(template: assertions.Template, role_fragment: str) -> str:
    policies = template.find_resources("AWS::IAM::Policy")
    return json.dumps(
        [
            policy["Properties"]["PolicyDocument"]
            for logical_id, policy in policies.items()
            if logical_id.startswith(role_fragment)
        ]
    )


def test_dsql_de_una_region_protegido(template: assertions.Template) -> None:
    template.has_resource(
        "AWS::DSQL::Cluster",
        {
            "Properties": {"DeletionProtectionEnabled": True},
            "DeletionPolicy": "Retain",
        },
    )
    (cluster,) = template.find_resources("AWS::DSQL::Cluster").values()
    assert "MultiRegionProperties" not in cluster["Properties"]


def test_sin_vpc_ni_rds(template: assertions.Template) -> None:
    template.resource_count_is("AWS::EC2::VPC", 0)
    template.resource_count_is("AWS::EC2::NatGateway", 0)
    template.resource_count_is("AWS::RDS::DBInstance", 0)


def test_la_api_no_es_administradora_de_la_base(template: assertions.Template) -> None:
    api = _role_policies(template, "ApiRole")
    assert "dsql:DbConnect" in api
    assert "dsql:DbConnectAdmin" not in api
    assert "dsql:DbConnectAdmin" in _role_policies(template, "MigrateServiceRole")


def test_s3_privado_y_solo_por_tls(template: assertions.Template) -> None:
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            }
        },
    )
    template.has_resource_properties(
        "AWS::S3::BucketPolicy",
        {
            "PolicyDocument": Match.object_like(
                {
                    "Statement": Match.array_with(
                        [
                            Match.object_like(
                                {
                                    "Effect": "Deny",
                                    "Condition": {"Bool": {"aws:SecureTransport": "false"}},
                                }
                            )
                        ]
                    )
                }
            )
        },
    )


def test_api_con_concurrencia_acotada_y_url_publica(template: assertions.Template) -> None:
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {"ReservedConcurrentExecutions": 10, "Timeout": 29, "MemorySize": 1024},
    )
    template.has_resource_properties("AWS::Lambda::Url", {"AuthType": "NONE"})
    # Sin CORS en la Function URL: lo resuelve FastAPI.
    (url,) = template.find_resources("AWS::Lambda::Url").values()
    assert "Cors" not in url["Properties"]


def test_migraciones_antes_de_la_api(template: assertions.Template) -> None:
    triggers_found = template.find_resources("Custom::Trigger")
    assert len(triggers_found) == 1
    (trigger_id,) = triggers_found
    functions = template.find_resources(
        "AWS::Lambda::Function", {"Properties": {"ReservedConcurrentExecutions": 10}}
    )
    (api,) = functions.values()
    assert any(trigger_id in dependency for dependency in api["DependsOn"])


def test_pool_de_prod_protegido_con_la_url_de_amplify(template: assertions.Template) -> None:
    template.has_resource(
        "AWS::Cognito::UserPool",
        {
            "Properties": {"DeletionProtection": "ACTIVE"},
            "DeletionPolicy": "Retain",
        },
    )
    (client,) = template.find_resources("AWS::Cognito::UserPoolClient").values()
    callback = json.dumps(client["Properties"]["CallbackURLs"])
    assert "DefaultDomain" in callback
    assert "localhost" not in callback


def test_presupuesto_no_descuenta_creditos_y_sin_email_en_el_template(
    template: assertions.Template,
) -> None:
    template.has_resource_properties(
        "AWS::Budgets::Budget",
        {
            "Budget": Match.object_like(
                {
                    "BudgetLimit": {"Amount": 20, "Unit": "USD"},
                    "CostTypes": {"IncludeCredit": False, "IncludeRefund": False},
                }
            )
        },
    )
    template.has_parameter("BudgetEmail", {"NoEcho": True})
    budget = json.dumps(template.find_resources("AWS::Budgets::Budget"))
    assert "@" not in budget
    assert '"Ref": "BudgetEmail"' in budget


def test_solo_entran_los_emails_permitidos(template: assertions.Template) -> None:
    (pool,) = template.find_resources("AWS::Cognito::UserPool").values()
    assert "PreSignUp" in pool["Properties"]["LambdaConfig"]
    template.has_parameter("AllowedEmails", {"NoEcho": True})
    functions = json.dumps(
        template.find_resources(
            "AWS::Lambda::Function",
            {
                "Properties": {
                    "Environment": {
                        "Variables": Match.object_like({"ALLOWED_EMAILS": Match.any_value()})
                    }
                }
            },
        )
    )
    assert '"Ref": "AllowedEmails"' in functions
    assert "@" not in functions


def test_web_con_reescritura_spa_y_csp(template: assertions.Template) -> None:
    (app,) = template.find_resources("AWS::Amplify::App").values()
    props = app["Properties"]
    assert props["CustomRules"][0]["Target"] == "/index.html"
    headers = props["CustomHeaders"]
    assert "script-src 'self'" in headers
    assert "frame-ancestors 'none'" in headers
    assert "unsafe-eval" not in headers
    template.has_resource_properties(
        "AWS::Amplify::Branch", {"BranchName": "main", "EnableAutoBuild": False}
    )


def test_solo_recursos_en_la_region_del_proyecto(template: assertions.Template) -> None:
    assert "us-east-1" not in json.dumps(template.to_json())
