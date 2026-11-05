from typing import Any

import pytest

from app.config import Settings
from app.migrate import grant_api_role


def settings(role: str = "gastos_api") -> Settings:
    values: dict[str, Any] = {
        "dsql_endpoint": "x.dsql.us-east-2.on.aws",
        "dsql_role": role,
        "s3_bucket": "b",
        "aws_region": "us-east-2",
    }
    return Settings(**values)


@pytest.mark.parametrize(
    ("role", "arn"),
    [
        ("gastos_api", "arn:aws:iam::123456789012:role/x'; DROP TABLE users; --"),
        ("gastos_api", ""),
        ("gastos; DROP TABLE users", "arn:aws:iam::123456789012:role/api"),
    ],
)
def test_rechaza_valores_que_irian_a_sql_sin_parametros(role: str, arn: str) -> None:
    with pytest.raises(ValueError, match="inválido"):
        grant_api_role(settings(role), arn)
