import pytest

from app.text import search_key


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Ñandutí", "nanduti"),
        ("  ARROZ  ", "arroz"),
        ("Café Molido", "cafe molido"),
        ("Verdulería", "verduleria"),
    ],
)
def test_normaliza_para_buscar(value: str, expected: str) -> None:
    assert search_key(value) == expected
