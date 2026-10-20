"""Standbilder aus einem Video — für Vision/Format-Erkennung."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .probe import ProbeError, ffmpeg_exe, probe
from .spec import even


def frames(path, times=None, *, count: int | None = None, out_dir: str = "memory/screenshots",
           prefix: str | None = None, width: int | None = None) -> list[dict]:
    """PNGs aus einem Video schneiden.

    `times`: explizite Sekunden. Sonst `count` gleichmäßig verteilte Frames
    (Default 4) — über das Video verteilt, nicht am Anfang. `width` skaliert
    herunter (Seitenverhältnis bleibt). Rückgabe: `[{'t', 'path', 'size'}]`.
    """
    info = probe(path)
    duration = float(info.get("duration") or 0.0)

    if times is None:
        n = 4 if count is None else int(count)
        if n < 1:
            raise ValueError("count must be >= 1")
        if duration <= 0:
            raise ValueError("cannot spread frames: unknown duration, pass --at")
        times = [(i + 0.5) * duration / n for i in range(n)]
    else:
        times = [float(t) for t in times]
    if not times:
        raise ValueError("no times to extract")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = prefix or Path(str(path)).stem

    src_w, src_h = info["size"]
    if width:
        w = even(int(width))
        h = max(2, even(round(src_h * w / src_w)))
    else:
        w, h = src_w, src_h

    got: list[dict] = []
    for t in times:
        t = max(0.0, min(float(t), max(0.0, duration - 0.05)))
        target = out / f"{stem}-{int(round(t * 1000)):09d}.png"
        cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
               "-ss", f"{t:.3f}", "-i", str(path)]
        if width:
            cmd += ["-vf", f"scale={w}:-2"]
        cmd += ["-frames:v", "1", str(target)]

        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        if proc.returncode != 0 or not target.exists():
            detail = (proc.stderr or "").strip().splitlines()
            raise ProbeError(
                f"ffmpeg could not extract a frame at {t:.3f}s"
                + (f": {detail[-1]}" if detail else "")
            )
        got.append({"t": round(t, 3), "path": str(target), "size": [w, h]})

    return got
