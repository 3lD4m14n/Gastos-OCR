"""Salida estructurada del OCR. Los nombres coinciden con docs/spec.md y gt.json."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class Item(BaseModel):
    barcode: str | None
    raw_name: str
    quantity: Decimal = Decimal(1)
    unit_price: int | None
    line_total: int
    iva_rate: Literal[5, 10, 0] | None
    kind: Literal["item", "discount"] = "item"
    cut_at_edge: bool = False
    is_uncertain: bool = False
    category_hint: str | None = None


class ImageRead(BaseModel):
    photo_position: int
    has_header: bool
    items: list[Item]
    detected_total: int | None


class TicketOCR(BaseModel):
    merchant: str | None
    ruc: str | None
    purchased_at: datetime | None
    images: list[ImageRead]
