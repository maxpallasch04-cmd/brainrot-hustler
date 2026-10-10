"""Anonymous file hosting: give it a file, get a public URL back.

Two hosts, no API key required:

- **catbox** (``https://catbox.moe/user/api.php``) — permanent links, <= 200 MB.
- **litterbox** (``https://litterbox.catbox.moe/resources/internals/api.php``) —
  self-expiring links (``1h``/``12h``/``24h``/``72h``), <= 1 GB.

The API replies with the plain URL as text. Anonymous uploads just omit the
optional ``userhash``.
"""

from __future__ import annotations

import os
from pathlib import Path

import requests

CATBOX_API = "https://catbox.moe/user/api.php"
LITTERBOX_API = "https://litterbox.catbox.moe/resources/internals/api.php"

CATBOX_MAX_BYTES = 200 * 1024 * 1024          # 200 MB
LITTERBOX_MAX_BYTES = 1024 * 1024 * 1024      # 1 GB
LITTERBOX_TIMES = ("1h", "12h", "24h", "72h")  # allowed `expires` values

FILE_FIELD = "fileToUpload"

# catbox's nginx rejects the default python-requests User-Agent with HTTP 412.
USER_AGENT = "Mozilla/5.0 (compatible; BrainrotHustler/1.0)"


class UploadError(RuntimeError):
    """Upload failed (bad input, size limit, or host error)."""


def _is_url(text: str) -> bool:
    return text.startswith("http://") or text.startswith("https://")


def _post_file(endpoint, filename, content, *, extra, timeout) -> str:
    """POST one file and return the URL the host answers with."""
    resp = requests.post(endpoint, data=dict(extra),
                         files={FILE_FIELD: (filename, content)}, timeout=timeout,
                         headers={"User-Agent": USER_AGENT})
    text = (resp.text or "").strip()
    if resp.status_code != 200 or not _is_url(text):
        raise UploadError(f"upload failed (HTTP {resp.status_code}): {text[:300]!r}")
    return text


def upload_bytes(content: bytes, filename: str, *, expires: str | None = None,
                 userhash: str | None = None, timeout: int = 180) -> str:
    """Upload raw bytes; returns the public URL.

    ``expires`` (one of ``LITTERBOX_TIMES``) routes to litterbox (temporary);
    otherwise catbox (permanent).
    """
    size = len(content)
    extra: dict[str, str] = {"reqtype": "fileupload"}
    if userhash:
        extra["userhash"] = userhash

    if expires is not None:
        if expires not in LITTERBOX_TIMES:
            raise UploadError(f"expires must be one of {LITTERBOX_TIMES}, "
                              f"got {expires!r}")
        if size > LITTERBOX_MAX_BYTES:
            raise UploadError(f"file too large for litterbox: {size} B > "
                              f"{LITTERBOX_MAX_BYTES} B")
        extra["time"] = expires
        return _post_file(LITTERBOX_API, filename, content, extra=extra,
                          timeout=timeout)

    if size > CATBOX_MAX_BYTES:
        raise UploadError(f"file too large for catbox: {size} B > "
                          f"{CATBOX_MAX_BYTES} B")
    return _post_file(CATBOX_API, filename, content, extra=extra, timeout=timeout)


def upload_file(path, *, expires: str | None = None, userhash: str | None = None,
                timeout: int = 180) -> str:
    """Upload a file from disk; returns the public URL."""
    p = Path(path)
    if not p.is_file():
        raise UploadError(f"not a file: {p}")
    return upload_bytes(p.read_bytes(), p.name, expires=expires,
                        userhash=userhash, timeout=timeout)


def upload(source, *, filename: str | None = None, expires: str | None = None,
           userhash: str | None = None, timeout: int = 180) -> str:
    """Upload either a path (str/Path) or raw bytes; returns the public URL."""
    if isinstance(source, (bytes, bytearray)):
        if not filename:
            raise UploadError("filename is required when uploading raw bytes")
        return upload_bytes(bytes(source), filename, expires=expires,
                            userhash=userhash, timeout=timeout)
    return upload_file(source, expires=expires, userhash=userhash,
                       timeout=timeout)
