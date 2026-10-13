"""Download a URL to a local file.

Companion to the uploader: give it a link, get a saved file. Anonymous, no
credentials. Follows redirects, sets a browser-like User-Agent (some hosts
reject the default python-requests UA), and infers the filename from
Content-Disposition or the URL when no destination is given.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

DEFAULT_MAX_BYTES = 1024 * 1024 * 1024  # 1 GiB safety cap

# Some hosts reject the default python-requests User-Agent (e.g. HTTP 412).
USER_AGENT = "Mozilla/5.0 (compatible; BrainrotHustler/1.0)"


class DownloadError(RuntimeError):
    """Download failed (bad URL, HTTP error, too large, or write error)."""


def _filename_from_disposition(value: str | None) -> str | None:
    if not value:
        return None
    m = re.search(r"filename\*?=(?:UTF-8''|\")?([^\";]+)", value, re.IGNORECASE)
    return unquote(m.group(1).strip().strip('"')) if m else None


def filename_from(url: str, content_disposition: str | None = None) -> str:
    """Best-effort filename: Content-Disposition, else URL path, else 'download.bin'."""
    name = _filename_from_disposition(content_disposition)
    if not name:
        name = unquote(Path(urlparse(url).path).name)
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", (name or "").strip()).strip("._")
    return name or "download.bin"


def download(url, dest=None, *, out_dir=None, timeout: int = 180,
             max_bytes: int | None = DEFAULT_MAX_BYTES, chunk: int = 1 << 20,
             session=None) -> dict:
    """Download `url` to a file and return metadata.

    `dest`: explicit output file path (wins). Otherwise the file is written into
    `out_dir` (default: cwd) under the inferred filename. `max_bytes` guards
    against runaway downloads (None disables the cap).
    """
    if not (str(url).startswith("http://") or str(url).startswith("https://")):
        raise DownloadError(f"not an http(s) url: {url!r}")
    sess = session or requests
    resp = sess.get(str(url), stream=True, timeout=timeout, allow_redirects=True,
                    headers={"User-Agent": USER_AGENT})
    with resp:
        if resp.status_code != 200:
            raise DownloadError(f"download failed (HTTP {resp.status_code}) for {url}")
        name = filename_from(resp.url or str(url),
                             resp.headers.get("Content-Disposition"))
        path = Path(dest) if dest is not None else (Path(out_dir or ".") / name)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".part")
        total = 0
        try:
            with open(tmp, "wb") as fh:
                for block in resp.iter_content(chunk_size=chunk):
                    if not block:
                        continue
                    total += len(block)
                    if max_bytes is not None and total > max_bytes:
                        raise DownloadError(f"file exceeds max_bytes ({max_bytes})")
                    fh.write(block)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
        tmp.replace(path)
        return {"path": str(path), "bytes": total, "filename": path.name,
                "url": resp.url or str(url),
                "content_type": resp.headers.get("Content-Type")}
