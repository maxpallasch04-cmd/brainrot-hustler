"""Medien lesen über das ffmpeg-Binary - der einzige Weg für Audio und Frames.

Kein MoviePy: `editor.probe.ffmpeg_exe()` liefert das Binary
(`EDITOR_FFMPEG` → `ffmpeg` im PATH → `imageio-ffmpeg` als Fallback),
hier wird nur gestreamt und in numpy gepackt.

Alles wird **strömend** gelesen: kein vollständiges Video und keine komplette
Tonspur liegen je im Speicher.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import numpy as np

from editor.probe import ffmpeg_exe, probe

#: Abtastrate für die Lautheits-Hüllkurve. 8 kHz reicht für Peaks (Applaus,
#: Kommentator) und hält stundenlange VODs klein.
DEFAULT_PCM_RATE = 8000


def video_info(path) -> dict:
    """Größe, Dauer und Tonspur eines Videos (ffprobe)."""
    return probe(str(path))


def video_size(path) -> tuple[int, int]:
    width, height = video_info(path)["size"]
    return int(width), int(height)


def _stderr_text(handle) -> str:
    handle.seek(0)
    return handle.read().decode("utf-8", "replace").strip()[:300]


def read_frame_at(path, t: float) -> np.ndarray:
    """Ein RGB-Frame zum Zeitpunkt `t` (Sekunden), `H x W x 3`."""
    width, height = video_size(path)
    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-nostdin",
           "-ss", f"{max(0.0, float(t)):.3f}", "-i", str(path),
           "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    with tempfile.TemporaryFile() as err:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=err)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {_stderr_text(err)}")
        data = proc.stdout
    need = width * height * 3
    if len(data) < need:
        raise ValueError(f"no frame at {t}s in {path}")
    return np.frombuffer(data[:need], dtype=np.uint8).reshape(height, width, 3)


def iter_gray_frames(path, *, start: float = 0.0, end: float | None = None,
                     fps: float = 4.0, width: int = 160):
    """Graustufen-Frames als ``(index, ndarray)``, bereits auf `width` skaliert.

    ffmpeg skaliert und konvertiert, bevor die Daten ankommen - ein 1080p-Frame
    landet nie in Python.
    """
    src_w, src_h = video_size(path)
    out_w = max(2, int(width))
    out_h = int(round(src_h * out_w / float(src_w)))
    out_h = max(2, out_h - out_h % 2)
    start = max(0.0, float(start))

    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-nostdin",
           "-ss", f"{start:.3f}", "-i", str(path)]
    if end is not None:
        cmd += ["-t", f"{max(0.0, float(end) - start):.3f}"]
    cmd += ["-vf", f"fps={fps},scale={out_w}:{out_h}:flags=area,format=gray",
            "-f", "rawvideo", "-pix_fmt", "gray", "-"]

    frame_bytes = out_w * out_h
    err = tempfile.TemporaryFile()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err)
    try:
        index = 0
        while True:
            buf = proc.stdout.read(frame_bytes)
            if not buf or len(buf) < frame_bytes:
                break
            yield index, np.frombuffer(buf, dtype=np.uint8).reshape(out_h, out_w)
            index += 1
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg failed: {_stderr_text(err)}")
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.stdout.close()
        err.close()


def iter_pcm(path, *, rate: int = DEFAULT_PCM_RATE, block: int = 1 << 17):
    """Mono-PCM als float32-Blöcke (Werte -1..1)."""
    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-nostdin",
           "-i", str(path), "-vn", "-ac", "1", "-ar", str(rate),
           "-f", "f32le", "-"]

    err = tempfile.TemporaryFile()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err)
    try:
        while True:
            chunk = proc.stdout.read(block * 4)
            if not chunk:
                break
            yield np.frombuffer(chunk, dtype="<f4")
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg failed: {_stderr_text(err)}")
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.stdout.close()
        err.close()
