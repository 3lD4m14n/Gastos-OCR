#!/usr/bin/env python3
import aws_cdk as cdk

from infra.gastos_stack import GastosStack
from infra.infra_stack import InfraStack

app = cdk.App()
# Todos los recursos regionales del proyecto van en esta Región.
env = cdk.Environment(region="us-east-2")
# El Client ID de Google es público; el secreto vive en Secrets Manager.
google_client_id = app.node.get_context("gastos:googleClientId")

InfraStack(app, "InfraStack", env=env, google_client_id=google_client_id)
GastosStack(app, "GastosProd", env=env, google_client_id=google_client_id)

app.synth()
