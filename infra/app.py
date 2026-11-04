#!/usr/bin/env python3
import aws_cdk as cdk

from stacks.gastos_stack import GastosStack

app = cdk.App()
# Todos los recursos regionales del proyecto van en esta Región.
GastosStack(app, "GastosStack", env=cdk.Environment(region="us-east-2"))
app.synth()
