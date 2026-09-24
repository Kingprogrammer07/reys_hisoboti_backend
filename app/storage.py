"""Photo object storage.

Cloudflare R2 is S3-compatible, so boto3 can talk to it through the account
endpoint. The module is lazy: local SQLite/disk fallback still works without
R2 credentials.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import config


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


def photo_key(entry_id: int, idx: int) -> str:
    prefix = config.CLOUDFLARE_R2_PREFIX
    base = f"entries/{int(entry_id)}/{int(idx)}"
    return f"{prefix}/{base}" if prefix else base


def put_photo(entry_id: int, idx: int, data: bytes, mime: str) -> StoredPhoto | None:
    """Store photo in R2 when enabled; return None for SQLite fallback."""
    if not r2_enabled():
        return None
    key = photo_key(entry_id, idx)
    resp = _r2_client().put_object(
        Bucket=config.CLOUDFLARE_R2_BUCKET,
        Key=key,
        Body=data,
        ContentType=mime or "image/jpeg",
        CacheControl="private, max-age=86400",
    )
    return StoredPhoto(
        backend="r2",
        key=key,
        size=len(data),
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
