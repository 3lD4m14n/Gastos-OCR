"""Corre el merge contra cada ticket de docs/fixtures/receipts, en todos los órdenes."""

import json
from decimal import Decimal
from itertools import permutations
from pathlib import Path
from typing import Any

import pytest

from app.ocr.merge import merge
from app.ocr.schemas import ImageRead
from tests.ocr.transcription import parse_image

RECEIPTS = Path(__file__).resolve().parents[3] / "docs" / "fixtures" / "receipts"
AHORRAZO = RECEIPTS / "ahorrazo-2026-09-25" / "gt.json"
CASES = sorted(RECEIPTS.glob("*/gt.json"))


def load(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def arrivals(gt: dict[str, Any]) -> list[list[ImageRead]]:
    """Cada permutación de fotos, con `photo_position` según el orden de llegada."""
    return [
        [parse_image(raw["transcription"], position) for position, raw in enumerate(perm, start=1)]
        for perm in permutations(gt["images"])
    ]


def test_hay_fixtures() -> None:
    assert AHORRAZO in CASES


@pytest.mark.parametrize("path", CASES, ids=lambda path: path.parent.name)
def test_merge_reproduce_gt_en_cualquier_orden(path: Path) -> None:
    gt = load(path)
    expected = [
        (
            item["raw_name"],
            Decimal(str(item["quantity"])),
            item["unit_price"],
            item["line_total"],
            item["is_uncertain"],
        )
        for item in gt["items"]
    ]

    for images in arrivals(gt):
        result = merge(images)
        got = [
            (i.raw_name, i.quantity, i.unit_price, i.line_total, i.is_uncertain)
            for i in result.items
        ]
        assert got == expected
        assert result.items_sum == gt["detected_total"]
        assert result.detected_total == gt["detected_total"]
        assert result.sum_matches is True
        assert result.warnings == []


def test_ahorrazo_detalle() -> None:
    gt = load(AHORRAZO)
    in_order, reversed_order = arrivals(gt)

    assert merge(in_order).image_order == [1, 2]
    assert merge(reversed_order).image_order == [2, 1]
    for images in (in_order, reversed_order):
        result = merge(images)
        assert result.overlaps == [4]
        assert len(result.items) == 23
        assert result.items_sum == 189_400


def test_ahorrazo_sin_deduplicar_sobran_lineas() -> None:
    images = arrivals(load(AHORRAZO))[0]
    lines = [item for image in images for item in image.items]
    assert len(lines) == 27
    assert sum(item.line_total for item in lines) == 211_200


def test_ahorrazo_conserva_compras_repetidas_reales() -> None:
    names = [item.raw_name for item in merge(arrivals(load(AHORRAZO))[0]).items]
    assert names.count("REXONA DEO CR") == 2
    assert names.count("MARIELA ARROZ") == 2
    assert names.count("NORTE ATUN GR") == 3
    assert names.count("POLIFOAM FIBR") == 2
