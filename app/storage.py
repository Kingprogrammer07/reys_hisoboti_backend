"""Photo object storage and WebP optimization.

Cloudflare R2 is S3-compatible, so boto3 can talk to it through the account
endpoint. The module is lazy: local SQLite/disk fallback still works without
R2 credentials.

Features:
- WebP automatic conversion with 90-95% quality (standard: 92%).
- Apple iOS HEIC / HEIF format auto-decoding via pillow-heif.
- EXIF auto-rotation to fix sideways/upside-down phone photos.
- Highly organized, intuitive Cloudflare R2 folder hierarchy:
    prefix/kargolar/{cargo_code}/{reys_code}/{box_code}_foto_{idx+1}.webp
    or prefix/reyslar/{reys_code}/{box_code}_foto_{idx+1}.webp
    or prefix/yozuvlar/partiya_{entry_id}/{box_code}_foto_{idx+1}.webp
"""
from __future__ import annotations

from dataclasses import dataclass
import io
import logging
from typing import Optional, Tuple

from PIL import Image, ImageOps
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pass

from . import config

log = logging.getLogger("reys.storage")


@dataclass(frozen=True)
class StoredPhoto:
    backend: str
    key: str
    size: int
    etag: str | None = None


class StorageUnavailable(RuntimeError):
    pass


def r2_enabled() -> bool:
    return config.PHOTO_STORAGE_BACKEND == "r2"


def _r2_endpoint() -> str:
    return f"https://{config.CLOUDFLARE_R2_ACCOUNT_ID}.r2.cloudflarestorage.com"


def _r2_client():
    if not r2_enabled():
        raise StorageUnavailable("R2 bulutli xotirasi yoqilmagan")
    missing = [
        name for name, value in (
            ("CLOUDFLARE_R2_ACCOUNT_ID", config.CLOUDFLARE_R2_ACCOUNT_ID),
            ("CLOUDFLARE_R2_ACCESS_KEY_ID", config.CLOUDFLARE_R2_ACCESS_KEY_ID),
            ("CLOUDFLARE_R2_SECRET_ACCESS_KEY", config.CLOUDFLARE_R2_SECRET_ACCESS_KEY),
            ("CLOUDFLARE_R2_BUCKET", config.CLOUDFLARE_R2_BUCKET),
        )
        if not value
    ]
    if missing:
        raise StorageUnavailable(f"R2 sozlamalari to'liq emas: {', '.join(missing)}")
    try:
        import boto3
        from botocore.config import Config
    except ModuleNotFoundError as exc:
        raise StorageUnavailable("boto3 kutubxonasi o'rnatilmagan") from exc
    return boto3.client(
        "s3",
        endpoint_url=_r2_endpoint(),
        aws_access_key_id=config.CLOUDFLARE_R2_ACCESS_KEY_ID,
        aws_secret_access_key=config.CLOUDFLARE_R2_SECRET_ACCESS_KEY,
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


def optimize_and_convert_to_webp(
    data: bytes,
    quality: int = 92,
    max_dimension: int = 2560,
) -> Tuple[bytes, str]:
    """Convert any photo (JPEG, PNG, iOS HEIC/HEIF, WEBP) to WebP format.
    
    - Corrects EXIF rotation (prevents sideways phone photos).
    - Preserves alpha transparency when needed.
    - Compresses with 90-95% quality (default: 92%).
    - Caps dimension at 2560px to preserve performance on mobile devices.
    Returns: (webp_bytes, 'image/webp').
    """
    if not data:
        return data, "image/webp"

    try:
        with Image.open(io.BytesIO(data)) as img:
            # 1. Correct orientation according to EXIF tags
            try:
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass

            # 2. Color mode handling
            if img.mode in ("RGBA", "LA", "P"):
                if img.mode == "P":
                    img = img.convert("RGBA")
            else:
                img = img.convert("RGB")

            # 3. Prevent huge 48MP+ mobile photos from overloading clients
            w, h = img.size
            if max(w, h) > max_dimension:
                scale = max_dimension / float(max(w, h))
                new_size = (int(w * scale), int(h * scale))
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            # 4. Save as WebP
            buf = io.BytesIO()
            img.save(
                buf,
                format="WEBP",
                quality=max(80, min(100, quality)),
                method=4,
            )
            return buf.getvalue(), "image/webp"
    except Exception as exc:
        log.warning("Image WebP conversion failed: %s, using original bytes", exc)
        return data, "image/jpeg"


def photo_key(
    entry_id: int,
    idx: int,
    cargo_code: str = "",
    reys_code: str = "",
    box_code: str = "",
    ext: str = "webp",
) -> str:
    """Generate a clean, intuitive, folder-structured S3/R2 object key.
    
    Hierarchy in R2:
    - With Cargo & Reys:  kargolar/{cargo_code}/{reys_code}/{box_code}_foto_{idx+1}.webp
    - With Reys only:     reyslar/{reys_code}/{box_code}_foto_{idx+1}.webp
    - Fallback:           yozuvlar/partiya_{entry_id}/{box_code}_foto_{idx+1}.webp
    """
    prefix = (config.CLOUDFLARE_R2_PREFIX or "").strip("/")

    def _sanitize(val: str, fallback: str) -> str:
        s = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in (val or "").strip())
        cleaned = s.strip("._-")
        return cleaned if cleaned else fallback

    clean_box = _sanitize(box_code, f"quti_{entry_id}")
    file_name = f"{clean_box}_foto_{idx + 1}.{ext}"

    if cargo_code and reys_code:
        c_code = _sanitize(cargo_code, "noma'lum_kargo")
        r_code = _sanitize(reys_code, f"reys_{entry_id}")
        base = f"kargolar/{c_code}/{r_code}/{file_name}"
    elif reys_code:
        r_code = _sanitize(reys_code, f"reys_{entry_id}")
        base = f"reyslar/{r_code}/{file_name}"
    else:
        base = f"yozuvlar/partiya_{entry_id}/{file_name}"

    return f"{prefix}/{base}" if prefix else base


def put_photo(
    entry_id: int,
    idx: int,
    data: bytes,
    mime: str = "image/jpeg",
    cargo_code: str = "",
    reys_code: str = "",
    box_code: str = "",
    quality: int = 92,
) -> StoredPhoto | None:
    """Optimize, convert to WebP, and store photo in Cloudflare R2."""
    if not r2_enabled():
        return None

    # Convert to WebP (90-95% quality)
    webp_data, webp_mime = optimize_and_convert_to_webp(data, quality=quality)
    key = photo_key(
        entry_id=entry_id,
        idx=idx,
        cargo_code=cargo_code,
        reys_code=reys_code,
        box_code=box_code,
        ext="webp",
    )

    resp = _r2_client().put_object(
        Bucket=config.CLOUDFLARE_R2_BUCKET,
        Key=key,
        Body=webp_data,
        ContentType=webp_mime,
        CacheControl="public, max-age=31536000, immutable",
    )
    return StoredPhoto(
        backend="r2",
        key=key,
        size=len(webp_data),
        etag=(resp.get("ETag") or "").strip('"') or None,
    )


def get_photo(key: str) -> bytes:
    obj = _r2_client().get_object(Bucket=config.CLOUDFLARE_R2_BUCKET, Key=key)
    return obj["Body"].read()


def delete_photo(key: str) -> None:
    if not r2_enabled() or not key:
        return
    _r2_client().delete_object(Bucket=config.CLOUDFLARE_R2_BUCKET, Key=key)


def public_url(key: str) -> str | None:
    if not config.CLOUDFLARE_R2_PUBLIC_BASE_URL or not key:
        return None
    return f"{config.CLOUDFLARE_R2_PUBLIC_BASE_URL}/{key.lstrip('/')}"
