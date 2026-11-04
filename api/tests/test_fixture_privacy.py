"""Las fotos de los fixtures no deben llevar EXIF: suele traer GPS y datos del celular."""

from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parents[2] / "docs" / "fixtures"
JPEGS = sorted(p for p in FIXTURES.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg"})


def jpeg_markers(data: bytes) -> set[int]:
    """Marcadores de los segmentos previos a los datos de la imagen."""
    assert data[:2] == b"\xff\xd8", "no es un JPEG"
    markers: set[int] = set()
    position = 2
    while position + 4 <= len(data) and data[position] == 0xFF:
        marker = data[position + 1]
        if marker == 0xDA:
            break
        markers.add(marker)
        position += 2 + int.from_bytes(data[position + 2 : position + 4])
    return markers


def test_detecta_exif() -> None:
    with_exif = b"\xff\xd8\xff\xe1\x00\x04Ex\xff\xda"
    assert 0xE1 in jpeg_markers(with_exif)


@pytest.mark.parametrize("path", JPEGS, ids=lambda path: path.name)
def test_fixture_sin_exif(path: Path) -> None:
    assert 0xE1 not in jpeg_markers(path.read_bytes()), f"{path} tiene EXIF o XMP"
