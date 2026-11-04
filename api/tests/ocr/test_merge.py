"""Reglas del merge con datos sintéticos, para los casos que el fixture no cubre."""

from itertools import permutations

import pytest

from app.ocr.merge import merge, order_images, overlap, same
from app.ocr.schemas import ImageRead, Item


def item(
    name: str,
    total: int = 1_000,
    barcode: str | None = None,
    *,
    cut_at_edge: bool = False,
) -> Item:
    return Item(
        barcode=barcode,
        raw_name=name,
        unit_price=total,
        line_total=total,
        iva_rate=10,
        cut_at_edge=cut_at_edge,
    )


def photo(
    position: int,
    items: list[Item],
    *,
    header: bool = False,
    total: int | None = None,
) -> ImageRead:
    return ImageRead(
        photo_position=position,
        has_header=header,
        items=items,
        detected_total=total,
    )


def names(images: list[ImageRead]) -> list[str]:
    return [i.raw_name for i in merge(images).items]


P, Q, R, S, X = (item(name, 1_000 * n) for n, name in enumerate("PQRSX", start=1))


def test_codigo_compara_los_ultimos_ocho_digitos() -> None:
    assert same(item("A", barcode="784076300762"), item("B", barcode="76300762"))
    assert not same(item("A", barcode="784076300762"), item("A", barcode="784076300763"))


def test_mismo_codigo_con_otro_monto_no_coincide() -> None:
    assert not same(item("A", 1_000, "784076300762"), item("A", 2_000, "784076300762"))


def test_sin_codigo_compara_el_nombre_normalizado() -> None:
    assert same(item("PLUSBELLE JABON"), item("plusbelle-jabon"))
    assert same(item("PLUSBELLE JABON", barcode="1"), item("PLUSBELLE JABN"))
    assert not same(item("OMO DT PO LV"), item("COLGATE CREMA"))


@pytest.mark.parametrize(("ratio", "expected"), [(84.99, False), (85.0, True)])
def test_umbral_de_nombre(monkeypatch: pytest.MonkeyPatch, ratio: float, expected: bool) -> None:
    monkeypatch.setattr("rapidfuzz.fuzz.ratio", lambda *_: ratio)
    assert same(item("A"), item("B")) is expected


def test_overlap_elige_el_bloque_mas_largo_con_duplicado_interno() -> None:
    assert overlap([P, Q, Q], [Q, Q, R]) == 2
    result = merge([photo(1, [P, Q, Q], header=True), photo(2, [Q, Q, R])])
    assert [i.raw_name for i in result.items] == ["P", "Q", "Q", "R"]
    assert result.overlaps == [2]


def test_duplicados_en_medio_de_la_foto_se_conservan() -> None:
    images = [photo(1, [P, Q, Q, R], header=True), photo(2, [R, S])]
    # El borde tiene k = 1 sin total: R queda marcado, pero los Q no se tocan.
    assert names(images).count("Q") == 2


def test_borde_ambiguo_fusiona_si_asi_cuadra_el_total() -> None:
    result = merge(
        [
            photo(1, [P, X], header=True),
            photo(2, [X, R], total=P.line_total + X.line_total + R.line_total),
        ]
    )
    assert [i.raw_name for i in result.items] == ["P", "X", "R"]
    assert result.overlaps == [1]
    assert result.sum_matches is True
    assert result.warnings == []


def test_borde_ambiguo_conserva_la_compra_real_si_asi_cuadra_el_total() -> None:
    result = merge(
        [
            photo(1, [P, X], header=True),
            photo(2, [X, R], total=P.line_total + 2 * X.line_total + R.line_total),
        ]
    )
    assert [i.raw_name for i in result.items] == ["P", "X", "X", "R"]
    assert result.overlaps == [0]
    assert result.sum_matches is True
    assert result.warnings == []
    assert all(i.flags == [] for i in result.items)


@pytest.mark.parametrize(("total", "sum_matches"), [(999, False), (None, None)])
def test_borde_ambiguo_sin_resolver_marca_la_segunda_copia(
    total: int | None, sum_matches: bool | None
) -> None:
    result = merge([photo(1, [P, X], header=True), photo(2, [X, R], total=total)])

    assert [i.raw_name for i in result.items] == ["P", "X", "X", "R"]
    assert [i.flags for i in result.items] == [[], [], ["possible_duplicate"], []]
    assert result.sum_matches is sum_matches
    assert [(w.code, w.photo_positions) for w in result.warnings] == [
        ("possible_duplicate", (1, 2))
    ]


def test_varios_bordes_ambiguos_eligen_la_combinacion_que_cuadra() -> None:
    total = P.line_total + 2 * X.line_total + Q.line_total + R.line_total
    result = merge(
        [
            photo(1, [P, X], header=True),
            photo(2, [X, Q]),
            photo(3, [Q, R], total=total),
        ]
    )
    assert [i.raw_name for i in result.items] == ["P", "X", "X", "Q", "R"]
    assert result.overlaps == [0, 1]
    assert result.warnings == []


def test_linea_cortada_se_descarta_antes_de_ordenar() -> None:
    first = photo(2, [P, Q, R, item("S", S.line_total, cut_at_edge=True)])
    second = photo(1, [Q, R, S, X])

    assert [i.photo_position for i in order_images([second, first])] == [2, 1]
    result = merge([second, first])
    assert [i.raw_name for i in result.items] == ["P", "Q", "R", "S", "X"]
    assert result.overlaps == [2]


def test_foto_sin_lineas_en_comun_avisa_posible_tramo_faltante() -> None:
    result = merge([photo(1, [P, Q], header=True), photo(2, [R, S], total=10_000)])
    assert [(w.code, w.photo_positions) for w in result.warnings] == [("possible_gap", (1, 2))]
    assert "entre la foto 1 y la 2" in result.warnings[0].message


def test_una_sola_foto() -> None:
    result = merge([photo(1, [P, Q], header=True, total=P.line_total + Q.line_total)])
    assert [i.raw_name for i in result.items] == ["P", "Q"]
    assert result.overlaps == []
    assert result.sum_matches is True
    assert result.warnings == []


def test_descuento_negativo_suma_al_total() -> None:
    discount = Item(
        barcode=None,
        raw_name="DESCUENTO",
        unit_price=None,
        line_total=-500,
        iva_rate=None,
        kind="discount",
    )
    result = merge([photo(1, [P, discount], header=True, total=P.line_total - 500)])
    assert result.items_sum == 500
    assert result.sum_matches is True


def test_seis_fotos_en_cualquier_orden_dan_el_mismo_ticket() -> None:
    lines = [item(f"PRODUCTO {n:02}", 1_000 + n, f"7840000000{n:02}") for n in range(16)]
    total = sum(i.line_total for i in lines)
    # Cada tramo repite dos líneas con el siguiente para que el borde no sea ambiguo.
    tramos = [lines[0:5], lines[3:8], lines[6:10], lines[8:12], lines[10:14], lines[12:16]]

    for perm in list(permutations(range(6)))[::37]:
        images = [
            photo(
                position,
                tramos[index],
                header=index == 0,
                total=total if index == 5 else None,
            )
            for position, index in enumerate(perm, start=1)
        ]
        result = merge(images)
        assert [i.raw_name for i in result.items] == [i.raw_name for i in lines]
        assert result.sum_matches is True
        assert result.warnings == []


@pytest.mark.parametrize("count", [0, 7])
def test_rechaza_cantidades_de_fotos_fuera_de_rango(count: int) -> None:
    with pytest.raises(ValueError, match="de 1 a 6 fotos"):
        merge([photo(n, [P]) for n in range(count)])
