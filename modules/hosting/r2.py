"""Cloudflare R2 upload backend (S3-compatible). The only upload target.

Give it a file, get a public URL back — backed by your own bucket. Works from
datacenter IPs (no VPS/VPN block) and has no commercial-use restriction.

Configuration comes from the environment (see ``TOOLS.md``):

    R2_ACCOUNT_ID          Cloudflare account id (32 hex chars)
    R2_ACCESS_KEY_ID       R2 API token access key id
    R2_SECRET_ACCESS_KEY   R2 API token secret
    R2_BUCKET              bucket name
    R2_PUBLIC_BASE_URL     public base url, e.g. https://pub-xxxx.r2.dev
                           or a custom domain like https://vids.example.com
    R2_KEEP                optional, newest objects to retain (default 1)
    R2_QUOTA_GB            optional, soft storage quota in GB (default 10)
    R2_ENDPOINT            optional, default https://<account>.r2.cloudflarestorage.com
    R2_PREFIX              optional key prefix inside the bucket, default "videos/"

Storage is kept small by pruning after each upload (see ``prune``): only the
newest ``R2_KEEP`` objects survive, and the total stays under ``R2_QUOTA_GB``.

Requires ``boto3`` (see ``modules/requirements.txt``).
"""

from __future__ import annotations

import mimetypes
import os
import re
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PREFIX = "videos/"
DEFAULT_KEEP = 1
DEFAULT_QUOTA_GB = 10.0
REGION = "auto"
REQUIRED = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY",
            "R2_BUCKET", "R2_PUBLIC_BASE_URL")

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


class R2Error(RuntimeError):
    """R2 operation failed (missing config, boto3 missing, or bucket error)."""


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name, default)
    return value.strip() if isinstance(value, str) else value


def _env_number(name: str, default, cast):
    raw = _env(name)
    if raw is None or raw == "":
        return default
    try:
        return cast(raw)
    except (TypeError, ValueError):
        return default


def config() -> dict:
    """Read and validate the R2 configuration from the environment."""
    missing = [name for name in REQUIRED if not _env(name)]
    if missing:
        raise R2Error("missing R2 config: " + ", ".join(missing)
                      + " — set the R2_* env vars (OpenClaw store/env, see TOOLS.md)")
    account = _env("R2_ACCOUNT_ID")
    prefix = (_env("R2_PREFIX") or DEFAULT_PREFIX).strip("/")
    return {
        "endpoint": _env("R2_ENDPOINT") or f"https://{account}.r2.cloudflarestorage.com",
        "access_key_id": _env("R2_ACCESS_KEY_ID"),
        "secret_access_key": _env("R2_SECRET_ACCESS_KEY"),
        "bucket": _env("R2_BUCKET"),
        "public_base_url": _env("R2_PUBLIC_BASE_URL").rstrip("/"),
        "prefix": prefix + "/" if prefix else "",
    }


def is_configured() -> bool:
    """True when every required R2 variable is set."""
    try:
        config()
        return True
    except R2Error:
        return False


def keep_count() -> int:
    """How many newest objects to retain (``R2_KEEP``, default 1)."""
    return max(0, _env_number("R2_KEEP", DEFAULT_KEEP, int))


def quota_bytes() -> int:
    """Soft storage quota in bytes (``R2_QUOTA_GB``, default 10 GB)."""
    gb = _env_number("R2_QUOTA_GB", DEFAULT_QUOTA_GB, float)
    return int(gb * 1024 ** 3)


def object_key(filename, *, prefix: str | None = None, when: datetime | None = None) -> str:
    """Build a collision-free object key, e.g. ``videos/2026-10-12/20261012-100000-clip.mp4``."""
    when = when or datetime.now(timezone.utc)
    name = _SAFE.sub("-", Path(str(filename)).name).strip("-.") or "upload.bin"
    return f"{prefix if prefix is not None else DEFAULT_PREFIX}{when:%Y-%m-%d}/{when:%Y%m%d-%H%M%S}-{name}"


def public_url(key: str, base: str | None = None) -> str:
    """Join a key with the public base url (r2.dev subdomain or custom domain)."""
    base = (base or config()["public_base_url"]).rstrip("/")
    return f"{base}/{key.lstrip('/')}"


def _client(cfg: dict, timeout: int = 180):
    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise R2Error("boto3 is required for R2 uploads: pip install -r requirements.txt") from exc
    return boto3.client(
        "s3",
        endpoint_url=cfg["endpoint"],
        aws_access_key_id=cfg["access_key_id"],
        aws_secret_access_key=cfg["secret_access_key"],
        region_name=REGION,
        config=Config(signature_version="s3v4", connect_timeout=30, read_timeout=timeout,
                      retries={"max_attempts": 3, "mode": "standard"}),
    )


def upload_bytes(content: bytes, filename: str, *, key: str | None = None,
                 content_type: str | None = None, timeout: int = 180) -> str:
    """Upload raw bytes; returns the public URL. Does not prune (see ``prune``)."""
    cfg = config()
    key = key or object_key(filename, prefix=cfg["prefix"])
    ctype = content_type or mimetypes.guess_type(str(filename))[0] or "application/octet-stream"
    try:
        _client(cfg, timeout).put_object(
            Bucket=cfg["bucket"], Key=key, Body=content,
            ContentType=ctype, CacheControl="public, max-age=31536000")
    except Exception as exc:  # botocore raises many error types
        raise R2Error(f"R2 upload failed: {exc}") from exc
    return public_url(key, cfg["public_base_url"])


def upload_file(path, *, key: str | None = None, timeout: int = 180) -> str:
    """Upload a file from disk; returns the public URL. Does not prune."""
    p = Path(path)
    if not p.is_file():
        raise R2Error(f"not a file: {p}")
    return upload_bytes(p.read_bytes(), p.name, key=key, timeout=timeout)


def upload(source, *, filename: str | None = None, timeout: int = 180) -> str:
    """Upload either a path (str/Path) or raw bytes; returns the public URL."""
    if isinstance(source, (bytes, bytearray)):
        if not filename:
            raise R2Error("filename is required when uploading raw bytes")
        return upload_bytes(bytes(source), filename, timeout=timeout)
    return upload_file(source, timeout=timeout)


def list_objects(*, prefix: str | None = None, client=None, cfg: dict | None = None) -> list[dict]:
    """List stored objects as ``{key, size, last_modified}`` (one paged call)."""
    cfg = cfg or config()
    client = client or _client(cfg)
    prefix = cfg["prefix"] if prefix is None else prefix
    out: list[dict] = []
    token = None
    while True:
        kwargs = {"Bucket": cfg["bucket"], "Prefix": prefix}
        if token:
            kwargs["ContinuationToken"] = token
        resp = client.list_objects_v2(**kwargs)
        for obj in resp.get("Contents") or []:
            out.append({"key": obj["Key"], "size": int(obj.get("Size", 0)),
                        "last_modified": obj.get("LastModified")})
        if resp.get("IsTruncated") and resp.get("NextContinuationToken"):
            token = resp["NextContinuationToken"]
        else:
            break
    return out


def _order(obj: dict):
    return (obj.get("last_modified") or _EPOCH, obj["key"])


def _delete(client, bucket: str, keys: list[str]) -> list[str]:
    """Bulk-delete keys (one request per 1000)."""
    for i in range(0, len(keys), 1000):
        chunk = keys[i:i + 1000]
        client.delete_objects(
            Bucket=bucket,
            Delete={"Objects": [{"Key": k} for k in chunk], "Quiet": True})
    return keys


def prune(*, keep: int | None = None, quota: int | None = None, protect=(),
          client=None, cfg: dict | None = None) -> dict:
    """Delete old objects: keep the newest ``keep`` and stay under ``quota`` bytes.

    ``protect`` lists keys that must never be deleted (e.g. the object just
    uploaded). One list call + one bulk delete call — no per-object round-trips.
    """
    cfg = cfg or config()
    client = client or _client(cfg)
    keep = keep_count() if keep is None else max(0, int(keep))
    quota = quota_bytes() if quota is None else int(quota)
    protect = {str(k) for k in protect}

    objects = list_objects(client=client, cfg=cfg)
    newest = sorted(objects, key=_order, reverse=True)

    survivors = {obj["key"] for obj in newest[:keep]}
    survivors |= {obj["key"] for obj in newest if obj["key"] in protect}

    total = sum(obj["size"] for obj in objects if obj["key"] in survivors)
    for obj in reversed(newest):  # drop oldest survivors until under quota
        if total <= quota:
            break
        if obj["key"] not in survivors or obj["key"] in protect:
            continue
        survivors.discard(obj["key"])
        total -= obj["size"]

    doomed = [obj["key"] for obj in objects if obj["key"] not in survivors]
    deleted = _delete(client, cfg["bucket"], doomed) if doomed else []
    return {"deleted": deleted, "kept": sorted(survivors), "bytes": total,
            "quota_bytes": quota}


def usage(*, client=None, cfg: dict | None = None) -> dict:
    """Report stored object count, used bytes, and remaining space to the quota."""
    cfg = cfg or config()
    client = client or _client(cfg)
    objects = list_objects(client=client, cfg=cfg)
    used = sum(obj["size"] for obj in objects)
    quota = quota_bytes()
    return {"objects": len(objects), "bytes": used, "quota_bytes": quota,
            "free_bytes": max(0, quota - used),
            "keys": sorted(obj["key"] for obj in objects)}
