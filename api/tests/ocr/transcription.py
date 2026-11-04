"""Convierte la transcripción de gt.json en lo que entregaría el modelo para una foto."""

import re
from decimal import Decimal

from app.ocr.schemas import ImageRead, Item

QTY_RE = re.compile(r"^\s*(\d+(?:,\d+)?)\s+x\s+([\d.]+)\s+Gs\s*$")
ITEM_RE = re.compile(r"^(\d+)\s+(.+?)\s+([\d.]+)G\s+(\d+)\s*$")
TOTAL_RE = re.compile(r"TOTAL\s+GS:\s*([\d.]+)")


def gs(value: str) -> int:
    return int(value.replace(".", ""))


def parse_image(transcription: str, photo_position: int) -> ImageRead:
    rows = transcription.splitlines()
    items: list[Item] = []
    total: int | None = None
    for index, row in enumerate(rows):
        match = ITEM_RE.match(row)
        if match:
            qty = QTY_RE.match(rows[index - 1]) if index > 0 else None
            items.append(
                Item.model_validate(
                    {
                        "barcode": match[1],
                        "raw_name": match[2].strip(),
                        "quantity": Decimal(qty[1].replace(",", ".")) if qty else Decimal(1),
                        "unit_price": gs(qty[2]) if qty else gs(match[3]),
                        "line_total": gs(match[3]),
                        "iva_rate": int(match[4]),
                    }
                )
            )
        found_total = TOTAL_RE.search(row)
        if found_total:
            total = gs(found_total[1])
    return ImageRead(
        photo_position=photo_position,
        has_header=any("Timbrado" in row or "SUPERMERCADO" in row for row in rows),
        items=items,
        detected_total=total,
    )
