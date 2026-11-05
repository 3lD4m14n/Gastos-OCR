from typing import Any

import pytest

from lambdas.pre_signup.index import handler


def event(email: str | None) -> dict[str, Any]:
    attributes = {} if email is None else {"email": email}
    return {
        "triggerSource": "PreSignUp_ExternalProvider",
        "request": {"userAttributes": attributes},
        "response": {},
    }


@pytest.mark.parametrize("email", ["persona@example.com", " Persona@Example.COM "])
def test_permite_el_email_de_la_lista(monkeypatch: pytest.MonkeyPatch, email: str) -> None:
    monkeypatch.setenv("ALLOWED_EMAILS", "persona@example.com, otra@example.com")
    original = event(email)
    assert handler(original, None) == original


@pytest.mark.parametrize("email", ["ajena@example.com", "persona@example.com.ar", "", None])
def test_rechaza_lo_que_no_esta_en_la_lista(
    monkeypatch: pytest.MonkeyPatch, email: str | None
) -> None:
    monkeypatch.setenv("ALLOWED_EMAILS", "persona@example.com")
    with pytest.raises(PermissionError):
        handler(event(email), None)


@pytest.mark.parametrize("configured", [None, "", " , "])
def test_sin_lista_no_entra_nadie(monkeypatch: pytest.MonkeyPatch, configured: str | None) -> None:
    if configured is None:
        monkeypatch.delenv("ALLOWED_EMAILS", raising=False)
    else:
        monkeypatch.setenv("ALLOWED_EMAILS", configured)
    with pytest.raises(PermissionError):
        handler(event("persona@example.com"), None)
