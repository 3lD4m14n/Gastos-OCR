"""Camino completo del merge con un ticket inventado, para que siempre corra en CI."""

from itertools import permutations

from app.ocr.merge import merge
from tests.ocr.transcription import parse_image

FOTO_1 = """SUPERMERCADO DE PRUEBA
Timbrado:00000000
       1  x        4.000 Gs
100000000001 JABON TOCADOR    4.000G 10
       2  x        1.500 Gs
100000000002 FIDEO CODITO     3.000G 5
       1  x        2.500 Gs
100000000003 YERBA MATE       2.500G 10
       1  x        2.500 Gs
100000000003 YERBA MATE       2.500G 10"""

FOTO_2 = """       1  x        2.500 Gs
100000000003 YERBA MATE       2.500G 10
       1  x        2.500 Gs
100000000003 YERBA MATE       2.500G 10
       1  x        6.000 Gs
100000000004 ACEITE GIRASOL   6.000G 5
       1  x        1.000 Gs
100000000005 SAL FINA         1.000G 10"""

FOTO_3 = """       1  x        1.000 Gs
100000000005 SAL FINA         1.000G 10
       1  x        1.000 Gs
100000000005 SAL FINA         1.000G 10
       1  x        3.000 Gs
100000000006 AZUCAR           3.000G 10
TOTAL GS: 23.000"""

ESPERADO = [
    "JABON TOCADOR",
    "FIDEO CODITO",
    "YERBA MATE",
    "YERBA MATE",
    "ACEITE GIRASOL",
    "SAL FINA",
    "SAL FINA",
    "AZUCAR",
]


def test_une_fotos_en_cualquier_orden_y_conserva_compras_repetidas() -> None:
    for perm in permutations([FOTO_1, FOTO_2, FOTO_3]):
        images = [parse_image(text, n) for n, text in enumerate(perm, start=1)]
        result = merge(images)
        assert [item.raw_name for item in result.items] == ESPERADO
        assert result.items_sum == 23_000
        assert result.sum_matches is True
        assert result.warnings == []
