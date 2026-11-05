#!/usr/bin/env python3
import aws_cdk as cdk

from infra.infra_stack import InfraStack

app = cdk.App()
InfraStack(
    app,
    "InfraStack",
    # Todos los recursos regionales del proyecto van en esta Región.
    env=cdk.Environment(region="us-east-2"),
    # El Client ID de Google es público; el secreto vive en Secrets Manager.
    google_client_id=app.node.get_context("gastos:googleClientId"),
)

app.synth()
