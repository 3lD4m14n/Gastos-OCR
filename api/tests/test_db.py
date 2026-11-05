from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.db import MAX_ATTEMPTS, run_transaction


class _Orig(Exception):
    def __init__(self, sqlstate: str) -> None:
        super().__init__(sqlstate)
        self.sqlstate = sqlstate


def _failure(sqlstate: str) -> DBAPIError:
    return DBAPIError("COMMIT", {}, _Orig(sqlstate))


@pytest.fixture
def sqlite() -> Any:
    return create_engine("sqlite://")


def test_reintenta_el_conflicto_de_serializacion(sqlite: Any) -> None:
    calls = 0

    def work(_session: Session) -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise _failure("40001")
        return "listo"

    assert run_transaction(work, engine=sqlite) == "listo"
    assert calls == 3


def test_se_rinde_tras_el_maximo_de_intentos(sqlite: Any) -> None:
    calls = 0

    def work(_session: Session) -> None:
        nonlocal calls
        calls += 1
        raise _failure("40001")

    with pytest.raises(DBAPIError):
        run_transaction(work, engine=sqlite)
    assert calls == MAX_ATTEMPTS


def test_no_reintenta_otros_errores(sqlite: Any) -> None:
    calls = 0

    def work(_session: Session) -> None:
        nonlocal calls
        calls += 1
        raise _failure("23505")

    with pytest.raises(DBAPIError):
        run_transaction(work, engine=sqlite)
    assert calls == 1
