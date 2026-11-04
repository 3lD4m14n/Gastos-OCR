# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow>=11"]
# ///
"""Tapa zonas de una foto de ticket y genera un JPEG nuevo sin metadatos.

Las coordenadas son píxeles de la imagen ya orientada: x0,y0,x1,y1.

    uv run --script docs/fixtures/sanitize_image.py original.jpg limpia.jpg \\
        --box 1112,1520,1795,1652 --box 683,1836,1275,1948
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


def parse_box(value: str) -> tuple[int, int, int, int]:
    parts = [int(part) for part in value.split(",")]
    if len(parts) != 4 or parts[0] >= parts[2] or parts[1] >= parts[3]:
        raise argparse.ArgumentTypeError(f"caja inválida: {value!r}; se espera x0,y0,x1,y1")
    return parts[0], parts[1], parts[2], parts[3]


def sanitize(source: Path, target: Path, boxes: list[tuple[int, int, int, int]]) -> None:
    with Image.open(source) as original:
        oriented = ImageOps.exif_transpose(original).convert("RGB")

    # Relleno opaco: un desenfoque o pixelado se puede llegar a revertir.
    draw = ImageDraw.Draw(oriented)
    for box in boxes:
        draw.rectangle(box, fill=(0, 0, 0))

    # Copiar solo los píxeles deja atrás EXIF, GPS, XMP, ICC y miniaturas embebidas.
    clean = Image.new("RGB", oriented.size)
    clean.paste(oriented)
    clean.save(target, format="JPEG", quality=92, optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--box", type=parse_box, action="append", default=[])
    args = parser.parse_args()
    if args.source.resolve() == args.target.resolve():
        parser.error("la salida debe ser otro archivo; el original se conserva hasta revisar")
    sanitize(args.source, args.target, args.box)


if __name__ == "__main__":
    main()
