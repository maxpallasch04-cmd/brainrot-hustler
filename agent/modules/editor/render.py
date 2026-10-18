"""Rendern: validieren, Graph bauen, ein ffmpeg-Lauf."""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

from .graph import build
from .probe import ProbeError, ffmpeg_exe, probe
from .spec import Spec, SpecError, coerce
from .validate import validate


def _probes_for(rec: Spec) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for clip in rec.data.get("clips", []):
        path = str(rec.resolve(str(clip["source"])))
        if path in out:
            continue
        try:
            out[path] = probe(path)
        except ProbeError as exc:
            raise SpecError(str(exc)) from exc
    return out


def command(rec: Spec, out: str, *, overwrite: bool = False,
            preset: str = "veryfast", crf: int = 20,
            transition: float | None = None) -> dict:
    """Baut die ffmpeg-Argumentliste (ohne Ausführung)."""
    if transition is None:
        transition = rec.data.get("transition", 0.0)
    probes = _probes_for(rec)
    built = build(rec, probes, transition=transition)

    cmd = [ffmpeg_exe(), "-hide_banner", "-nostdin", "-loglevel", "error",
           "-y" if overwrite else "-n"]

    for item in built["inputs"]:
        if item["image"]:
            cmd += ["-i", item["path"]]
            continue
        if item.get("ss"):
            cmd += ["-ss", f"{float(item['ss']):.3f}"]
        if item.get("to") is not None:
            cmd += ["-to", f"{float(item['to']):.3f}"]
        cmd += ["-i", item["path"]]

    cmd += ["-filter_complex", built["filter_complex"], "-map", f"[{built['vout']}]"]
    if built["aout"]:
        cmd += ["-map", f"[{built['aout']}]"]

    cmd += ["-c:v", "libx264", "-preset", preset, "-crf", str(int(crf)),
            "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    if built["aout"]:
        cmd += ["-c:a", "aac", "-b:a", "160k"]
    else:
        cmd += ["-an"]

    cmd += ["-progress", "pipe:1", "-nostats", str(out)]
    built["command"] = cmd
    return built


def render(spec, out: str | None = None, *, overwrite: bool = False,
           dry_run: bool = False, progress: bool = True,
           preset: str = "veryfast", crf: int = 20,
           transition: float | None = None,
           report: dict | None = None) -> dict:
    """Rezept rendern. Wirft `SpecError` bei Validierungsfehlern."""
    rec = coerce(spec)
    check = report if report is not None else validate(rec)
    if not check["ok"]:
        first = check["errors"][0]
        raise SpecError(
            f"spec invalid: {first['code']} at {first['where']}: {first['message']}"
        )

    target = out or rec.data.get("out")
    if not target:
        raise SpecError("no output path: pass out= or set 'out' in the spec")

    # `out` aus dem Rezept ist relativ zum Rezept, `--out` relativ zum cwd.
    out_path = Path(target) if out else rec.resolve(target)
    if out_path.parent and not out_path.parent.exists():
        out_path.parent.mkdir(parents=True, exist_ok=True)

    built = command(rec, str(out_path), overwrite=overwrite, preset=preset,
                    crf=crf, transition=transition)

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "out": str(out_path),
            "duration": round(built["duration"], 3),
            "command": built["command"],
            "filter_complex": built["filter_complex"],
        }

    if out_path.exists() and not overwrite:
        raise SpecError(f"output exists: {out_path} (use overwrite=True)")

    started = time.monotonic()
    errors: list[str] = []
    proc = subprocess.Popen(
        built["command"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    def drain():
        assert proc.stderr is not None
        for line in proc.stderr:
            line = line.rstrip()
            if line:
                errors.append(line)

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()

    total = built["duration"] or 0.0
    last = 0.0
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            if not progress or not total:
                continue
            key, _, value = line.strip().partition("=")
            if key != "out_time_us":
                continue
            try:
                done = int(value) / 1_000_000.0
            except ValueError:
                continue
            now = time.monotonic()
            if now - last >= 5.0:
                last = now
                pct = min(100.0, 100.0 * done / total)
                print(f"[render] {pct:5.1f}% ({done:.1f}/{total:.1f}s)",
                      file=sys.stderr, flush=True)
    finally:
        proc.wait()
        reader.join(timeout=5)

    if proc.returncode != 0:
        detail = "\n".join(errors[-8:]) or f"exit code {proc.returncode}"
        raise SpecError(f"ffmpeg failed: {detail}")

    if not out_path.exists():
        raise SpecError(f"ffmpeg finished but produced no file: {out_path}")

    try:
        info = probe(out_path)
    except ProbeError:
        info = {}

    return {
        "ok": True,
        "out": str(out_path),
        "duration": round(info.get("duration") or built["duration"], 3),
        "size": list(info.get("size") or built["size"]),
        "fps": built["fps"],
        "audio": bool(built["aout"]),
        "seconds": round(time.monotonic() - started, 2),
    }
