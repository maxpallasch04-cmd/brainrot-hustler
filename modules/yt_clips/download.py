"""Download a YouTube video with yt-dlp.

Accepts a URL (watch / youtu.be / shorts). The file lands in
``out_dir/<ext-id>.<ext>``; existing files are reused unless ``overwrite=True``.
Returns ``{path, id, title, duration_s}``.
"""

from __future__ import annotations

import re
from pathlib import Path

DEFAULT_OUT_DIR = "clips"

_YT_ID = re.compile(r"(?:v=|youtu\.be/|shorts/|embed/|/v/)([A-Za-z0-9_-]{6,})")


def youtube_id(url: str) -> str | None:
    """Best-effort YouTube video id from a URL."""
    m = _YT_ID.search(str(url))
    return m.group(1) if m else None


def download(url: str, out_dir=DEFAULT_OUT_DIR, *, overwrite=False, quiet=True,
             subs_lang: str | None = None) -> dict:
    """Download one video (+ optional subtitles); returns the file facts.

    ``subs_lang`` (e.g. ``"en"``) also fetches the transcript (auto-captions,
    VTT) and returns its path as ``subs``.
    """
    try:
        import yt_dlp
    except ImportError as exc:  # pragma: no cover - depends on host
        raise RuntimeError("yt-dlp is not installed (python3 -m pip install yt-dlp)") from exc

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    opts = {
        "outtmpl": str(out / "%(id)s.%(ext)s"),
        "format": "mp4/best",
        "quiet": quiet,
        "no_warnings": quiet,
        "noprogress": True,
        "overwrites": bool(overwrite),
        "noplaylist": True,
    }
    if subs_lang:
        opts.update({
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": [subs_lang],
            "subtitlesformat": "vtt",
        })

    subs_path = None
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        requested = (info.get("requested_downloads") or [{}])[0]
        path = requested.get("filepath") or ydl.prepare_filename(info)
        for meta in (info.get("requested_subtitles") or {}).values():
            if meta.get("filepath"):
                subs_path = str(meta["filepath"])
                break
    return {"path": str(path), "id": info.get("id") or youtube_id(url),
            "title": info.get("title") or "", "duration_s": info.get("duration"),
            "chapters": info.get("chapters") or [], "subs": subs_path}
