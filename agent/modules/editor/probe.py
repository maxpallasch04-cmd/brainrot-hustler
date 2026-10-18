"""ffprobe-Wrapper: Maße, Dauer, Tonspur."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


class ProbeError(RuntimeError):
    """Datei nicht lesbar oder ffprobe/ffmpeg fehlt."""


def ffmpeg_exe() -> str:
    env = os.environ.get("EDITOR_FFMPEG")
    if env:
        return env
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:  # imageio-ffmpeg ist im Projekt ohnehin installiert
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # pragma: no cover - Umgebungssache
        raise ProbeError(
            "ffmpeg not found: install ffmpeg or set EDITOR_FFMPEG"
        ) from exc


def ffprobe_exe() -> str:
    env = os.environ.get("EDITOR_FFPROBE")
    if env:
        return env
    exe = shutil.which("ffprobe")
    if exe:
        return exe
    # ffprobe liegt üblicherweise neben ffmpeg
    ff = Path(ffmpeg_exe())
    for name in ("ffprobe.exe", "ffprobe"):
        cand = ff.with_name(name)
        if cand.exists():
            return str(cand)
    raise ProbeError("ffprobe not found: install ffmpeg or set EDITOR_FFPROBE")


def _rotation(stream: dict) -> int:
    for side in stream.get("side_data_list") or []:
        if "rotation" in side:
            try:
                return int(round(float(side["rotation"])))
            except (TypeError, ValueError):
                pass
    try:
        return int(round(float(stream.get("tags", {}).get("rotate", 0))))
    except (TypeError, ValueError):
        return 0


def probe(path) -> dict:
    """Datei auslesen: size, duration, has_audio.

    `size` ist die *Anzeige*-Größe (Rotation eingerechnet), also das, was
    ffmpeg beim Dekodieren liefert.
    """
    p = Path(path)
    if not p.exists():
        raise ProbeError(f"file not found: {p}")
    cmd = [
        ffprobe_exe(),
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(p),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ProbeError(f"ffprobe failed for {p}: {exc}") from exc
    if proc.returncode != 0:
        raise ProbeError(f"ffprobe failed for {p}: {proc.stderr.strip()}")

    try:
        info = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise ProbeError(f"ffprobe returned invalid JSON for {p}") from exc

    video = next((s for s in info.get("streams", [])
                  if s.get("codec_type") == "video"
                  and not s.get("disposition", {}).get("attached_pic")), None)
    if video is None:
        raise ProbeError(f"no video stream in {p}")

    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)
    rot = _rotation(video) % 360
    if rot in (90, 270):
        width, height = height, width

    duration = None
    for value in (info.get("format", {}).get("duration"), video.get("duration")):
        try:
            if value is not None:
                duration = float(value)
                break
        except (TypeError, ValueError):
            continue

    return {
        "path": str(p.resolve()),
        "width": width,
        "height": height,
        "size": (width, height),
        "duration": duration,
        "has_audio": any(s.get("codec_type") == "audio"
                         for s in info.get("streams", [])),
        "rotation": rot,
    }
