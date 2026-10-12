"""Subtitle handling: window a transcript, burn it into a video.

Subtitles stay a **separate artifact** (SRT/VTT) — this module never hides them
inside the video. Two independent steps:

- ``parse`` / ``window`` / ``to_srt`` / ``write_srt`` — pure file work: take a
  transcript (VTT or SRT) and cut a clip-relative window out of it.
- ``burn`` — render a subtitle file onto a video (ffmpeg + libass).

Both are reusable: burn it in, keep it as a soft track, or just read the text for
titles/descriptions.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


class SubtitleError(RuntimeError):
    """Subtitle work failed (bad file, or ffmpeg error)."""


# ---- parsing ------------------------------------------------------------

def _parse_ts(value: str) -> float:
    """'00:01:02.345' / '01:02,345' -> seconds."""
    parts = value.replace(",", ".").split(":")
    nums = [float(p) for p in parts if p != ""]
    while len(nums) < 3:
        nums.insert(0, 0.0)
    hours, minutes, seconds = nums[-3], nums[-2], nums[-1]
    return hours * 3600 + minutes * 60 + seconds


def _cue_from_block(lines: list[str]) -> dict | None:
    arrow = next((i for i, line in enumerate(lines) if "-->" in line), None)
    if arrow is None:
        return None
    left, _, right = lines[arrow].partition("-->")
    try:
        start = _parse_ts(left.strip().split()[0])
        end = _parse_ts(right.strip().split()[0])
    except (IndexError, ValueError):
        return None
    text = " ".join(TAG_RE.sub("", line) for line in lines[arrow + 1:])
    text = WS_RE.sub(" ", text).strip()
    if not text:
        return None
    return {"start": start, "end": end, "text": text}


def parse(text: str) -> list[dict]:
    """Parse VTT or SRT text into ``[{'start', 'end', 'text'}]``."""
    cues: list[dict] = []
    block: list[str] = []
    for raw in text.splitlines() + [""]:
        line = raw.lstrip("\ufeff").strip()
        if line == "":
            if block:
                cue = _cue_from_block(block)
                if cue:
                    cues.append(cue)
                block = []
            continue
        block.append(line)
    return cues


def load(path) -> list[dict]:
    """Read and parse a .vtt/.srt file."""
    return parse(Path(path).read_text(encoding="utf-8", errors="replace"))


# ---- cleanup ------------------------------------------------------------

def dedupe(cues: list[dict]) -> list[dict]:
    """Merge rolling auto-caption duplicates (identical consecutive text)."""
    out: list[dict] = []
    for cue in cues:
        if out and out[-1]["text"] == cue["text"]:
            out[-1]["end"] = max(out[-1]["end"], cue["end"])
            continue
        out.append(dict(cue))
    return out


# ---- numbers (scores announced in the commentary) -----------------------

_WORDS = {word: i for i, word in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve".split())}
_WORD = "|".join(_WORDS)
_DIGITS = re.compile(r"\b\d{1,2}(?:[.,]\d{1,3})?\b")
_SPOKEN = re.compile(rf"\b({_WORD})\s+point\s+((?:(?:{_WORD})\b\s*)+)")


def _spoken_value(match: re.Match) -> float | None:
    whole = _WORDS[match.group(1)]
    parts = re.findall(_WORD, match.group(2))
    digits = "".join(str(_WORDS[p]) for p in parts if _WORDS[p] < 10)
    return whole + float("0." + digits) if digits else None


def find_numbers(cues, *, lo: float | None = None, hi: float | None = None) -> list[dict]:
    """Score-like numbers in a transcript: ``[{'t', 'end', 'value', 'text', 'kind'}]``.

    Catches digits (``8.25``) and spelled-out scores (``eight point two five``).
    ``lo``/``hi`` optionally keep only values in range (e.g. 6…10 for a score).
    """
    hits: list[dict] = []
    for cue in cues:
        text = cue["text"]
        found: list[tuple[float, str]] = []
        for token in _DIGITS.findall(text):
            try:
                found.append((float(token.replace(",", ".")), "digit"))
            except ValueError:
                continue
        for match in _SPOKEN.finditer(text.lower()):
            value = _spoken_value(match)
            if value is not None:
                found.append((value, "words"))
        for value, kind in found:
            if lo is not None and value < lo:
                continue
            if hi is not None and value > hi:
                continue
            hits.append({"t": cue["start"], "end": cue["end"], "value": round(value, 3),
                         "text": text, "kind": kind})
    return hits


# ---- window -------------------------------------------------------------

def window(cues, start: float, end: float | None = None, *, offset: bool = True) -> list[dict]:
    """Cut cues to ``[start, end)``; with ``offset`` timestamps become clip-relative."""
    start = float(start)
    end = None if end is None else float(end)
    out: list[dict] = []
    for cue in cues:
        if cue["end"] <= start:
            continue
        if end is not None and cue["start"] >= end:
            break
        s = max(cue["start"], start)
        e = min(cue["end"], end) if end is not None else cue["end"]
        if e <= s:
            continue
        if offset:
            s, e = s - start, e - start
        out.append({"start": round(s, 3), "end": round(e, 3), "text": cue["text"]})
    return out


# ---- writing ------------------------------------------------------------

def _fmt_ts(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours:02d}:{minutes:02d}:{seconds % 60:06.3f}".replace(".", ",")


def to_srt(cues) -> str:
    """Render cues as SRT text."""
    blocks = []
    for i, cue in enumerate(cues, 1):
        blocks.append(f"{i}\n{_fmt_ts(cue['start'])} --> {_fmt_ts(cue['end'])}\n{cue['text']}\n")
    return "\n".join(blocks)


def write_srt(cues, path) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(to_srt(cues), encoding="utf-8")
    return str(target)


# ---- styling / burning --------------------------------------------------

def build_style(*, font=None, font_size=None, outline=None, alignment=None,
                margin_v=None, extra=None) -> str | None:
    """Build an ASS ``force_style`` string from simple options."""
    parts = []
    if font:
        parts.append(f"FontName={font}")
    if font_size:
        parts.append(f"FontSize={int(font_size)}")
    if outline is not None:
        parts.append(f"Outline={int(outline)}")
    if alignment is not None:
        parts.append(f"Alignment={int(alignment)}")
    if margin_v is not None:
        parts.append(f"MarginV={int(margin_v)}")
    if extra:
        parts.append(str(extra))
    return ",".join(parts) or None


def _ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # pragma: no cover - depends on host
        return "ffmpeg"


def _run_ffmpeg(cmd: list[str], cwd: str) -> None:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SubtitleError(f"ffmpeg failed: {(proc.stderr or '').strip()[:800]}")


def burn(video, subs, out, *, force_style: str | None = None, ffmpeg=None,
         crf: int = 20, preset: str = "medium", audio: str = "copy") -> str:
    """Render ``subs`` onto ``video`` (hardsub) and write ``out``.

    Runs in a temp dir with a simple file name so no path escaping is needed for
    ffmpeg's ``subtitles`` filter. Audio is copied (falls back to AAC on failure).
    """
    video_path, subs_path = Path(video).resolve(), Path(subs).resolve()
    if not video_path.is_file():
        raise SubtitleError(f"not a file: {video_path}")
    if not subs_path.is_file():
        raise SubtitleError(f"not a file: {subs_path}")
    out_path = Path(out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    exe = ffmpeg or _ffmpeg_exe()

    with tempfile.TemporaryDirectory() as tmp:
        shutil.copyfile(subs_path, Path(tmp) / "subs.srt")
        vf = "subtitles=subs.srt"
        if force_style:
            vf += f":force_style='{force_style}'"
        base = [exe, "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(video_path), "-vf", vf,
                "-c:v", "libx264", "-crf", str(int(crf)), "-preset", preset,
                "-pix_fmt", "yuv420p"]
        try:
            _run_ffmpeg([*base, "-c:a", audio, str(out_path)], tmp)
        except SubtitleError:
            _run_ffmpeg([*base, "-c:a", "aac", str(out_path)], tmp)
    return str(out_path)
