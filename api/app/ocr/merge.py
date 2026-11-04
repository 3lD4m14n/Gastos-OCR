"""Ordena las fotos de un ticket y une sus bordes de forma determinista.

Solo se compara el borde entre fotos consecutivas: los duplicados reales en medio
del ticket se conservan. Ver "Pipeline de OCR" en docs/spec.md.
"""

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from itertools import pairwise, permutations
from typing import Literal

from pydantic import BaseModel, Field
from rapidfuzz import fuzz

from app.ocr.schemas import ImageRead, Item

MAX_IMAGES = 6
MAX_OVERLAP = 12
BARCODE_SUFFIX = 8
NAME_MATCH_THRESHOLD = 85
ORDER_BONUS = 100

ItemFlag = Literal["possible_duplicate"]


class MergedItem(Item):
    flags: list[ItemFlag] = Field(default_factory=list)


class MergeWarning(BaseModel):
    code: Literal["possible_gap", "possible_duplicate"]
    photo_positions: tuple[int, int]
    message: str


class MergeResult(BaseModel):
    items: list[MergedItem]
    image_order: list[int]
    overlaps: list[int]
    items_sum: int
    detected_total: int | None
    sum_matches: bool | None
    warnings: list[MergeWarning]


@dataclass(frozen=True)
class _Candidate:
    items: tuple[Item, ...]
    overlaps: tuple[int, ...]
    # Bordes de una línea sin fusionar: (foto de la derecha en el orden, índice de la copia).
    kept_copies: tuple[tuple[int, int], ...]

    @property
    def total(self) -> int:
        return sum(item.line_total for item in self.items)


def norm(name: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", name.upper())


def same(x: Item, y: Item) -> bool:
    if x.line_total != y.line_total:
        return False
    if x.barcode and y.barcode:
        # El borde de la foto suele cortar los primeros dígitos.
        return x.barcode[-BARCODE_SUFFIX:] == y.barcode[-BARCODE_SUFFIX:]
    return fuzz.ratio(norm(x.raw_name), norm(y.raw_name)) >= NAME_MATCH_THRESHOLD


def overlap(a: Sequence[Item], b: Sequence[Item], max_k: int = MAX_OVERLAP) -> int:
    for k in range(min(len(a), len(b), max_k), 0, -1):
        if all(same(x, y) for x, y in zip(a[-k:], b[:k], strict=True)):
            return k
    return 0


def _complete_items(image: ImageRead) -> list[Item]:
    return [item for item in image.items if not item.cut_at_edge]


def order_images(images: Sequence[ImageRead]) -> list[ImageRead]:
    """Cabecera primero, TOTAL al final y, entre las demás, el máximo solapamiento.

    Se parte de `photo_position` para que un empate no dependa del orden de llegada.
    """
    usable = {image.photo_position: _complete_items(image) for image in images}

    def score(perm: tuple[ImageRead, ...]) -> int:
        lines = sum(
            overlap(usable[left.photo_position], usable[right.photo_position])
            for left, right in pairwise(perm)
        )
        return (
            lines
            + ORDER_BONUS * perm[0].has_header
            + ORDER_BONUS * (perm[-1].detected_total is not None)
        )

    by_position = sorted(images, key=lambda image: image.photo_position)
    best = by_position
    best_score = -1
    for perm in permutations(by_position):
        current = score(perm)
        if current > best_score:
            best, best_score = list(perm), current
    return best


def _candidates(images: Sequence[Sequence[Item]]) -> Iterator[_Candidate]:
    """Genera las uniones posibles; en un borde de una sola línea prueba primero fusionar."""

    def walk(
        index: int,
        merged: tuple[Item, ...],
        overlaps: tuple[int, ...],
        kept_copies: tuple[tuple[int, int], ...],
    ) -> Iterator[_Candidate]:
        if index == len(images):
            yield _Candidate(merged, overlaps, kept_copies)
            return
        current = images[index]
        k = overlap(merged, current)
        yield from walk(index + 1, merged + tuple(current[k:]), (*overlaps, k), kept_copies)
        if k == 1:
            yield from walk(
                index + 1,
                merged + tuple(current),
                (*overlaps, 0),
                (*kept_copies, (index, len(merged))),
            )

    yield from walk(1, tuple(images[0]), (), ())


def _choose(candidates: Sequence[_Candidate], total: int | None) -> _Candidate:
    if total is not None:
        for candidate in candidates:
            if candidate.total == total:
                return candidate
    # Sin una variante que cuadre se conservan las copias: en la revisión es más fácil
    # borrar un ítem de más que notar uno que falta. Es la última variante generada.
    return candidates[-1]


def merge(images: Sequence[ImageRead]) -> MergeResult:
    if not 1 <= len(images) <= MAX_IMAGES:
        raise ValueError(f"Se esperan de 1 a {MAX_IMAGES} fotos; llegaron {len(images)}")

    ordered = order_images(images)
    total = next(
        (image.detected_total for image in reversed(ordered) if image.detected_total is not None),
        None,
    )
    candidates = list(_candidates([_complete_items(image) for image in ordered]))
    chosen = _choose(candidates, total)
    resolved = total is not None and chosen.total == total

    kept_copies = dict(chosen.kept_copies)
    duplicates = set() if resolved else set(kept_copies.values())
    items = [
        MergedItem(
            **item.model_dump(),
            flags=["possible_duplicate"] if index in duplicates else [],
        )
        for index, item in enumerate(chosen.items)
    ]

    warnings: list[MergeWarning] = []
    for right_index, k in enumerate(chosen.overlaps, start=1):
        pair = (ordered[right_index - 1].photo_position, ordered[right_index].photo_position)
        if right_index in kept_copies:
            # Si el total confirma que son dos compras reales, no hay nada que avisar.
            if resolved:
                continue
            warnings.append(
                MergeWarning(
                    code="possible_duplicate",
                    photo_positions=pair,
                    message=(
                        f"Posible ítem duplicado en el borde entre la foto {pair[0]} y la {pair[1]}"
                    ),
                )
            )
        elif k == 0:
            warnings.append(
                MergeWarning(
                    code="possible_gap",
                    photo_positions=pair,
                    message=f"Puede faltar un tramo entre la foto {pair[0]} y la {pair[1]}",
                )
            )

    return MergeResult(
        items=items,
        image_order=[image.photo_position for image in ordered],
        overlaps=list(chosen.overlaps),
        items_sum=chosen.total,
        detected_total=total,
        sum_matches=None if total is None else chosen.total == total,
        warnings=warnings,
    )
