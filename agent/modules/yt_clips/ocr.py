"""Score OCR for the fixed ``boxes.score`` region.

The score board is static per video (only its content changes: empty or a
score), so this module never re-detects boxes. It crops the stored score box
from a frame and reads a value in **0.0–10.0**.

Engines (offline, no vision model):
- **tesseract** (primary) — local binary, ``TESSERACT_CMD`` or ``PATH``.
- **rapidocr** (fallback) — only if ``rapidocr_onnxruntime`` is installed.

Everything returns compact dicts — the caller decides whether to keep hits.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

NUMBER_RE = re.compile(r"\d{1,2}(?:[.,]\d{1,2})?")
_RAPID_ENGINE = None


def tesseract_path() -> str | None:
    """Locate the tesseract binary: env override, PATH, then common installs."""
    env = os.environ.get("TESSERACT_CMD")
    if env and Path(env).is_file():
        return env
    found = shutil.which("tesseract")
    if found:
        return found
    candidates = [
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path.home() / "AppData" / "Local" / "Tesseract-OCR" / "tesseract.exe",
    ]
    for path in candidates:
        if path.is_file():
            return str(path)
    return None


def parse_value(text: str, *, lo: float = 0.0, hi: float = 10.0):
    """Pick a 0.0–10.0 value from OCR text. Returns ``(value, raw)`` or None.

    Handles comma decimals and the usual OCR confusions (O→0, I/l→1).
    Prefers a decimal reading when several numbers are present.
    """
    candidates: list[tuple[float, str]] = []
    for token in re.split(r"\s+", str(text)):
        token = token.strip("()[]{}:;'\"|")
        if not token:
            continue
        # Only normalize a token that is already numeric-looking. Without this,
        # a label like "SCORE" becomes "SC0RE" and yields a fake 0.0.
        if re.fullmatch(r"[0-9OoIl|.,]+", token):
            for src, dst in (("O", "0"), ("o", "0"), ("I", "1"),
                             ("l", "1"), ("|", "1")):
                token = token.replace(src, dst)
        for match in NUMBER_RE.finditer(token):
            raw = match.group(0)
            try:
                value = float(raw.replace(",", "."))
            except ValueError:
                continue
            if lo <= value <= hi:
                candidates.append((round(value, 3), raw))
    if not candidates:
        return None
    decimals = [c for c in candidates if "." in c[1]]
    return (decimals or candidates)[0]


def _prepare(frame, box, *, pad: int = 6, scale: float = 3.0):
    """Crop the score box (clamped), grayscale, autocontrast, upscale."""
    from PIL import Image, ImageOps

    img = Image.fromarray(frame).convert("RGB")
    width, height = img.size
    x, y, w, h = (int(float(v)) for v in box)
    x = max(0, x - int(pad))
    y = max(0, y - int(pad))
    w = max(1, min(w + 2 * int(pad), width - x))
    h = max(1, min(h + 2 * int(pad), height - y))
    img = img.crop((x, y, x + w, y + h)).convert("L")
    img = ImageOps.autocontrast(img)
    if scale and float(scale) != 1.0:
        img = img.resize((max(1, int(round(img.width * scale))),
                          max(1, int(round(img.height * scale)))), Image.LANCZOS)
    return img


def _tesseract_read(img) -> str:
    """Run tesseract on one PIL image; returns its raw text."""
    from PIL import ImageOps

    exe = tesseract_path()
    if not exe:
        raise RuntimeError(
            "tesseract not found — install it or set TESSERACT_CMD")
    # Try normal and inverted (white-on-dark score boards are common).
    for variant in (img, ImageOps.invert(img)):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            path = Path(tmp.name)
        try:
            variant.save(path)
            proc = subprocess.run(
                [exe, str(path), "stdout", "--psm", "7", "-l", "eng",
                 "-c", "tessedit_char_whitelist=0123456789.,"],
                capture_output=True, text=True, timeout=20)
        finally:
            try:
                path.unlink()
            except OSError:
                pass
        text = (proc.stdout or "").strip()
        if proc.returncode == 0 and text:
            return text
    return ""


def _rapidocr_read(img) -> str:
    """Optional fallback: rapidocr_onnxruntime on a PIL image."""
    global _RAPID_ENGINE
    try:
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as exc:
        raise RuntimeError(
            "rapidocr_onnxruntime not installed — install it or use tesseract") from exc
    if _RAPID_ENGINE is None:
        _RAPID_ENGINE = RapidOCR()
    result, _ = _RAPID_ENGINE(np.array(img.convert("RGB"))[:, :, ::-1])
    if not result:
        return ""
    return " ".join(str(item[1]) for item in result if len(item) > 1)


def read_frame(frame, box, *, engine: str = "auto", pad: int = 6,
               scale: float = 3.0, lo: float = 0.0, hi: float = 10.0):
    """Read the score from one frame. Returns ``{value, raw, engine}`` or None."""
    img = _prepare(frame, box, pad=pad, scale=scale)
    order = [engine] if engine in ("tesseract", "rapidocr") else (
        ["tesseract"] if tesseract_path() else ["rapidocr"])
    for name in order:
        text = _tesseract_read(img) if name == "tesseract" else _rapidocr_read(img)
        got = parse_value(text, lo=lo, hi=hi)
        if got:
            return {"value": got[0], "raw": got[1], "engine": name}
    return None


def runs(hits, *, step: float = 1.0) -> list[dict]:
    """Merge consecutive equal values into runs: ``{start,end,value,count}``."""
    out: list[dict] = []
    for hit in hits:
        if (out and abs(out[-1]["value"] - hit["value"]) < 1e-6
                and hit["t"] - out[-1]["end"] <= float(step) * 1.5):
            out[-1]["end"] = hit["t"]
            out[-1]["count"] += 1
        else:
            out.append({"start": hit["t"], "end": hit["t"],
                        "value": hit["value"], "count": 1})
    for run in out:
        run["seconds"] = round(run["count"] * float(step), 3)
    return out


def scan(path, box, times, *, engine: str = "auto", pad: int = 6,
         scale: float = 3.0, lo: float = 0.0, hi: float = 10.0,
         debug_dir: str | None = None, step: float = 1.0) -> dict:
    """OCR the fixed box at ``times``. Returns hits, runs and the first hits."""
    from moviepy import VideoFileClip

    clip = VideoFileClip(str(path))
    hits: list[dict] = []
    checked = 0
    try:
        duration = float(clip.duration or 0.0)
        for t in times:
            t = max(0.0, min(float(t), max(0.0, duration - 0.05)))
            frame = clip.get_frame(t)
            got = read_frame(frame, box, engine=engine, pad=pad, scale=scale,
                             lo=lo, hi=hi)
            checked += 1
            if debug_dir:
                try:
                    _prepare(frame, box, pad=pad, scale=scale).save(
                        Path(debug_dir) / f"score-{t:09.2f}.png")
                except OSError:
                    pass
            if got:
                hits.append({"t": round(t, 3), **got})
    finally:
        clip.close()

    grouped = runs(hits, step=step)
    stable = next((r for r in grouped if r["count"] >= 2), None)
    first = hits[0] if hits else None
    return {
        "checked": checked,
        "hits": hits,
        "runs": grouped,
        "first": first,
        "first_stable": ({"t": stable["start"], "value": stable["value"]}
                         if stable else first),
        "engine": (hits[0]["engine"] if hits else
                   ("tesseract" if engine == "auto" and tesseract_path() else engine)),
    }
