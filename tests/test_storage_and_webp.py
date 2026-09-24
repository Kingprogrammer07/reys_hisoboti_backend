import io
from PIL import Image
import pytest

from app import config, storage


def test_photo_key_folder_hierarchy():
    # 1. With Cargo and Reys
    key1 = storage.photo_key(
        entry_id=5,
        idx=0,
        cargo_code="CARGO-TURK",
        reys_code="REYS-88",
        box_code="M104",
        ext="webp",
    )
    assert "kargolar/CARGO-TURK/REYS-88/M104_foto_1.webp" in key1

    # 2. With Reys only
    key2 = storage.photo_key(
        entry_id=12,
        idx=1,
        cargo_code="",
        reys_code="REYS-99",
        box_code="M105",
        ext="webp",
    )
    assert "reyslar/REYS-99/M105_foto_2.webp" in key2

    # 3. Fallback without cargo/reys
    key3 = storage.photo_key(
        entry_id=42,
        idx=2,
        cargo_code="",
        reys_code="",
        box_code="BOX-77",
        ext="webp",
    )
    assert "yozuvlar/partiya_42/BOX-77_foto_3.webp" in key3


def test_optimize_and_convert_to_webp():
    # Create sample RGB JPEG
    raw_img = Image.new("RGB", (100, 100), color=(255, 100, 50))
    buf = io.BytesIO()
    raw_img.save(buf, format="JPEG", quality=90)
    jpeg_bytes = buf.getvalue()

    # Convert to WebP
    webp_bytes, mime = storage.optimize_and_convert_to_webp(jpeg_bytes, quality=92)
    assert mime == "image/webp"
    assert len(webp_bytes) > 0

    # Verify converted image is valid WebP
    with Image.open(io.BytesIO(webp_bytes)) as converted:
        assert converted.format == "WEBP"
        assert converted.size == (100, 100)


def test_optimize_png_with_transparency_to_webp():
    # Create sample RGBA PNG
    raw_img = Image.new("RGBA", (80, 80), color=(0, 200, 100, 128))
    buf = io.BytesIO()
    raw_img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    # Convert to WebP
    webp_bytes, mime = storage.optimize_and_convert_to_webp(png_bytes, quality=92)
    assert mime == "image/webp"

    with Image.open(io.BytesIO(webp_bytes)) as converted:
        assert converted.format == "WEBP"
        assert converted.mode in ("RGBA", "RGB")
