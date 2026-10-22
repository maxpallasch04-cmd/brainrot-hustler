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

import os
import re
import subprocess
import tempfile
from pathlib import Path

from .probe import ffmpeg_exe

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
    raw = " ".join(lines[arrow + 1:]).strip()
    text = " ".join(TAG_RE.sub("", line) for line in lines[arrow + 1:])
    text = WS_RE.sub(" ", text).strip()
    if not text:
        return None
    return {"start": start, "end": end, "text": text, "raw": raw}


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


# ---- words (lazy, query-only) ------------------------------------------

INLINE_TS_RE = re.compile(r"<(\d{1,2}:\d{2}:\d{2}[.,]\d{3})>")
_SENT_END_RE = re.compile(r"[.!?…]['\")\]]*$")


def words(cues) -> list[dict]:
    """Word-level timings from cues, using YouTube inline ``<HH:MM:SS.mmm>`` tags.

    Returns ``[{'start', 'end', 'word', 'cue'}]``. Without inline tags the cue
    text is split into words with cue-level times and ``approx: True`` — the
    caller can then decide whether that precision is enough.
    """
    out: list[dict] = []
    for ci, cue in enumerate(cues):
        raw = cue.get("raw") or cue["text"]
        matches = list(INLINE_TS_RE.finditer(raw))
        if not matches:
            for token in cue["text"].split():
                out.append({"start": cue["start"], "end": cue["end"],
                            "word": token, "cue": ci, "approx": True})
            continue

        # Segments: (start, text) — text before the first tag belongs to cue start.
        segments: list[tuple[float, str]] = []
        pos = 0
        for i, match in enumerate(matches):
            if match.start() > pos:
                segments.append((cue["start"], raw[pos:match.start()]))
            start = _parse_ts(match.group(1))
            end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
            segments.append((start, raw[match.end():end]))
            pos = end

        for si, (seg_start, chunk) in enumerate(segments):
            chunk = WS_RE.sub(" ", TAG_RE.sub("", chunk)).strip()
            if not chunk:
                continue
            seg_end = segments[si + 1][0] if si + 1 < len(segments) else cue["end"]
            tokens = chunk.split()
            step = max(0.0, seg_end - seg_start) / len(tokens)
            for wi, token in enumerate(tokens):
                ws = seg_start + wi * step
                we = seg_start + (wi + 1) * step if len(tokens) > 1 else seg_end
                out.append({"start": round(ws, 3), "end": round(we, 3),
                            "word": token, "cue": ci})
    return out


def sentences(words_list, *, pause: float = 0.6) -> list[dict]:
    """Group words into sentences: punctuation or a pause between words."""
    out: list[dict] = []
    current: list[dict] = []
    for i, word in enumerate(words_list):
        current.append(word)
        nxt = words_list[i + 1] if i + 1 < len(words_list) else None
        break_here = (nxt is None
                      or _SENT_END_RE.search(word["word"]) is not None
                      or nxt["start"] - word["end"] >= float(pause))
        if break_here:
            out.append({"start": current[0]["start"], "end": current[-1]["end"],
                        "text": " ".join(w["word"] for w in current),
                        "words": current})
            current = []
    return out


def window_words(words_list, at: float, *, seconds: float = 3.0,
                 limit: int = 60) -> list[dict]:
    """Only the words around ``at`` (bounded by time and count) — token-cheap."""
    lo, hi = float(at) - float(seconds), float(at) + float(seconds)
    got = [w for w in words_list if w["end"] >= lo and w["start"] <= hi]
    return got[:max(1, int(limit))]


def snap(at: float, words_list, *, mode: str = "sentence",
         direction: str = "nearest", pause: float = 0.6) -> dict:
    """Nearest word/sentence boundary to ``at``.

    ``direction``: before (start <= at), after (end >= at), nearest.
    For sentences, a boundary is a sentence start (before) or sentence end
    (after); the returned ``text`` is that sentence.
    """
    at = float(at)
    if mode == "sentence":
        units = sentences(words_list, pause=pause)
        starts = [(u["start"], u) for u in units]
        ends = [(u["end"], u) for u in units]
    elif mode == "word":
        units = list(words_list)
        starts = [(u["start"], u) for u in units]
        ends = [(u["end"], u) for u in units]
    else:
        raise ValueError("mode must be 'sentence' or 'word'")

    candidates: list[tuple[float, dict, str]] = []
    if direction in ("before", "nearest"):
        before = [(t, u) for t, u in starts if t <= at]
        if before:
            t, u = max(before, key=lambda x: x[0])
            candidates.append((t, u, "before"))
    if direction in ("after", "nearest"):
        after = [(t, u) for t, u in ends if t >= at]
        if after:
            t, u = min(after, key=lambda x: x[0])
            candidates.append((t, u, "after"))
    if direction not in ("before", "after", "nearest"):
        raise ValueError("direction must be before/after/nearest")
    if not candidates:
        return {"at": at, "snapped": at, "delta": 0.0, "direction": direction,
                "mode": mode, "text": None}
    t, unit, used = min(candidates, key=lambda x: abs(x[0] - at))
    if direction != "nearest":
        used = direction
    return {"at": at, "snapped": round(t, 3), "delta": round(t - at, 3),
            "direction": used, "mode": mode,
            "text": unit.get("text") or unit.get("word")}


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


def _fmt_vtt_ts(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours:02d}:{minutes:02d}:{seconds % 60:06.3f}"


def to_vtt(cues) -> str:
    """Render cues as WebVTT — inline ``<ts>`` tags keep word timings."""
    blocks = ["WEBVTT", ""]
    for cue in cues:
        blocks.append(f"{_fmt_vtt_ts(cue['start'])} --> {_fmt_vtt_ts(cue['end'])}")
        blocks.append(cue.get("raw") or cue["text"])
        blocks.append("")
    return "\n".join(blocks)


def write_cues(cues, path) -> str:
    """Write cues; ``.vtt`` gets WebVTT (word tags), everything else SRT."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = to_vtt(cues) if target.suffix.lower() == ".vtt" else to_srt(cues)
    target.write_text(text, encoding="utf-8")
    return str(target)


def write_srt(cues, path) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(to_srt(cues), encoding="utf-8")
    return str(target)


# ---- transcription (local, faster-whisper) ------------------------------

def transcribe(video, out, *, model="base", lang=None, device="cpu",
               compute_type="int8", threads=0, vad=True, beam_size=5) -> dict:
    """Transcribe a video/audio file locally and write ``out`` (.vtt/.srt).

    Word timestamps go into the cue text as VTT ``<HH:MM:SS.mmm>`` tags, so the
    existing ``words()``/``snap()`` machinery works exactly like with YouTube
    auto-captions. ``burn`` strips the tags and rebuilds clean SRT, so the same
    file works for rendering.

    Needs ``faster-whisper``; the model is fetched once into the Hugging Face
    cache (``WHISPER_MODEL_DIR`` moves it, e.g. outside the repo).
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:  # pragma: no cover - depends on host
        raise SubtitleError(
            "faster-whisper is not installed (pip install faster-whisper)") from exc

    src = Path(video)
    if not src.is_file():
        raise SubtitleError(f"not a file: {src}")

    kwargs: dict = {"device": device, "compute_type": compute_type}
    if threads:
        kwargs["cpu_threads"] = int(threads)
    root = os.environ.get("WHISPER_MODEL_DIR", "").strip()
    if root:
        kwargs["download_root"] = root

    engine = WhisperModel(model, **kwargs)
    segments, info = engine.transcribe(str(src), language=lang or None,
                                       beam_size=int(beam_size),
                                       vad_filter=bool(vad),
                                       word_timestamps=True)
    cues: list[dict] = []
    words_count = 0
    for seg in segments:
        text = WS_RE.sub(" ", TAG_RE.sub("", seg.text or "")).strip()
        if not text:
            continue
        spoken = [w for w in (getattr(seg, "words", None) or [])
                  if (w.word or "").strip()]
        raw = None
        if spoken:
            words_count += len(spoken)
            raw = " ".join(f"<{_fmt_vtt_ts(w.start)}>{(w.word or '').strip()}"
                           for w in spoken)
        cues.append({"start": float(seg.start), "end": float(seg.end),
                     "text": text, "raw": raw})
    if not cues:
        raise SubtitleError(f"transcript is empty (no speech detected): {src}")

    path = write_cues(cues, out)
    return {"out": path, "cues": len(cues), "words": words_count,
            "model": model, "language": getattr(info, "language", None),
            "language_probability": round(
                float(getattr(info, "language_probability", 0.0) or 0.0), 3),
            "duration_s": round(float(getattr(info, "duration", 0.0) or 0.0), 3)}


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
    exe = ffmpeg or ffmpeg_exe()

    with tempfile.TemporaryDirectory() as tmp:
        if not load(subs_path):
            raise SubtitleError(f"no cues in {subs_path}")
        write_srt(load(subs_path), Path(tmp) / "subs.srt")
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
