"""Prueba del merge de fotos solapadas contra gt.json (ticket de 2 fotos)."""
import json
import re
from dataclasses import dataclass
from itertools import permutations

from rapidfuzz import fuzz

QTY_RE = re.compile(r"^\s*(\d+(?:,\d+)?)\s+x\s+([\d.]+)\s+Gs\s*$")
ITEM_RE = re.compile(r"^(\d+)\s+(.+?)\s+([\d.]+)G\s+(\d+)\s*$")
TOTAL_RE = re.compile(r"TOTAL\s+GS:\s*([\d.]+)")


@dataclass
class Line:
    barcode: str
    raw_name: str
    quantity: float
    unit_price: int
    line_total: int
    iva: int


def gs(s: str) -> int:
    return int(s.replace(".", ""))


def parse(transcription: str) -> tuple[list[Line], int | None, bool]:
    """Simula la salida del modelo: líneas de ítem de una foto, total si aparece, y si tiene cabecera."""
    rows = transcription.splitlines()
    out, total = [], None
    has_header = any("Timbrado" in r or "SUPERMERCADO" in r for r in rows)
    for i, r in enumerate(rows):
        m = ITEM_RE.match(r)
        if m:
            q = QTY_RE.match(rows[i - 1]) if i > 0 else None
            out.append(Line(m[1], m[2].strip(), float(q[1].replace(",", ".")) if q else 1,
                            gs(q[2]) if q else gs(m[3]), gs(m[3]), int(m[4])))
        t = TOTAL_RE.search(r)
        if t:
            total = gs(t[1])
    return out, total, has_header


def norm(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def same(x: Line, y: Line) -> bool:
    if x.line_total != y.line_total:
        return False
    if x.barcode and y.barcode:
        return x.barcode[-8:] == y.barcode[-8:]  # el borde de la foto suele cortar los primeros dígitos
    return fuzz.ratio(norm(x.raw_name), norm(y.raw_name)) >= 85


def overlap(a: list[Line], b: list[Line], max_k: int = 12) -> int:
    for k in range(min(len(a), len(b), max_k), 0, -1):
        if all(same(x, y) for x, y in zip(a[-k:], b[:k])):
            return k
    return 0


def order_images(imgs):
    """Elige el orden de fotos: cabecera primero, TOTAL al final, máximo solapamiento total."""
    best, best_score = None, -1
    for perm in permutations(range(len(imgs))):
        score = sum(overlap(imgs[perm[i]][0], imgs[perm[i + 1]][0]) for i in range(len(perm) - 1))
        if imgs[perm[0]][2]:
            score += 100
        if imgs[perm[-1]][1] is not None:
            score += 100
        if score > best_score:
            best, best_score = perm, score
    return list(best)


def merge(images: list[list[Line]]) -> tuple[list[Line], list[int]]:
    merged = list(images[0])
    ks = []
    for img in images[1:]:
        k = overlap(merged, img)
        ks.append(k)
        merged.extend(img[k:])
    return merged, ks


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "docs/fixtures/receipts/ahorrazo-2026-09-25/gt.json"
    gt = json.load(open(path))
    imgs = [parse(i["transcription"]) for i in gt["images"]]
    expected = [(it["raw_name"], it["line_total"]) for it in gt["items"]]

    for label, inp in [("orden correcto", imgs), ("orden invertido (como llegaron las fotos)", imgs[::-1])]:
        order = order_images(inp)
        merged, ks = merge([inp[i][0] for i in order])
        got = [(l.raw_name, l.line_total) for l in merged]
        total = next(t for _, t, _ in inp if t is not None)
        s = sum(l.line_total for l in merged)
        print(f"== {label}")
        print(f"   orden elegido: {order}, solapamiento detectado: {ks} líneas")
        print(f"   ítems: {len(got)} (esperados {len(expected)}), coincide con gt: {got == expected}")
        print(f"   suma: {s:,} Gs vs total impreso {total:,} Gs -> {'OK' if s == total else 'NO CUADRA'}")

    # Sin dedup: cuánto daría si se concatenan las fotos tal cual
    naive = sum(l.line_total for img in imgs for l in img[0])
    print(f"== sin deduplicar: {naive:,} Gs (sobra {naive - gt['detected_total']:,} Gs)")
