"""Download Twitch clips with yt-dlp.

Accepts a clip dict from `find_clips` (with 'url' or 'id'), a bare clip id, or a
full URL. Files are written to `out_dir/<clip-id>.mp4`; existing files are
skipped unless `overwrite=True`.
"""

from __future__ import annotations

import re
from pathlib import Path

DEFAULT_OUT_DIR = "clips"

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe(name: str) -> str:
    """Make a clip id safe to use as a file name."""
    return _UNSAFE.sub("_", str(name)).strip("_") or "clip"


def clip_url(clip) -> str:
    """Resolve a clip (URL string, id string, or dict) to a full URL."""
    if isinstance(clip, str):
        return clip if clip.startswith("http") else f"https://clips.twitch.tv/{clip}"
    if isinstance(clip, dict):
        if clip.get("url"):
            return clip["url"]
        if clip.get("id"):
            return f"https://clips.twitch.tv/{clip['id']}"
    raise ValueError("clip needs a 'url' or 'id'")


def clip_id(clip) -> str:
    """Best-effort clip id: from the dict, else the last URL path segment."""
    if isinstance(clip, dict) and clip.get("id"):
        return str(clip["id"])
    return clip_url(clip).rstrip("/").split("/")[-1]


def _download(clip, out_dir, *, overwrite=False, quiet=True):
    """Download one clip; return (path, skipped). Existing target -> skip."""
    out = Path(out_dir)
    name = _safe(clip_id(clip))
    target = out / f"{name}.mp4"
    if target.exists() and not overwrite:
        return str(target), True

    try:
        import yt_dlp
    except ImportError as exc:  # pragma: no cover - depends on host
        raise RuntimeError("yt-dlp is not installed (python3 -m pip install yt-dlp)") from exc

    out.mkdir(parents=True, exist_ok=True)
    opts = {
        "outtmpl": str(out / f"{name}.%(ext)s"),
        "format": "mp4/best",
        "quiet": quiet,
        "no_warnings": quiet,
        "noprogress": True,
        "overwrites": bool(overwrite),
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(clip_url(clip), download=True)
        path = ydl.prepare_filename(info)
    return path, False


def download_clip(clip, out_dir=DEFAULT_OUT_DIR, *, overwrite=False, quiet=True) -> str:
    """Download one clip and return the file path."""
    return _download(clip, out_dir, overwrite=overwrite, quiet=quiet)[0]


def download_clips(clips, out_dir=DEFAULT_OUT_DIR, *, overwrite=False, top=None,
                   quiet=True) -> dict:
    """Download a list of clips.

    Returns {'downloaded': [...], 'skipped': [...], 'failed': [{clip, error}]}.
    """
    clips = list(clips)
    if top is not None:
        clips = clips[: int(top)]
    downloaded: list[str] = []
    skipped: list[str] = []
    failed: list[dict] = []
    for clip in clips:
        try:
            path, was_skipped = _download(clip, out_dir, overwrite=overwrite, quiet=quiet)
            (skipped if was_skipped else downloaded).append(path)
        except Exception as exc:  # keep going; report per-clip failures
            try:
                label = clip_id(clip)
            except Exception:
                label = str(clip)
            failed.append({"clip": label, "error": str(exc)})
    return {"downloaded": downloaded, "skipped": skipped, "failed": failed}
