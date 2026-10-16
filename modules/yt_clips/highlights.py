"""Cost-free highlight detection for YT-clip sources.

Two local signals, no API calls:

1. **Chapters** — many sports videos ship chapter markers (yt-dlp gives them at
   download time). Free, already labelled.
2. **Audio peaks** — crowd roar / commentator excitement shows up as loudness
   spikes. The envelope is computed locally with MoviePy + NumPy.

The vision model is *not* used here — it is only needed once per video for the
format (see ``skills/ytclip``). An optional text-only ranking call can follow.
"""

from __future__ import annotations

import numpy as np

DEFAULT_FPS = 10          # envelope samples per second
DEFAULT_WINDOW_S = 1.0    # smoothing window
DEFAULT_K = 1.5           # peak threshold: mean + k * std
DEFAULT_LEAD = 6.0        # seconds before the peak
DEFAULT_LENGTH = 18.0     # candidate clip length
DEFAULT_MIN_GAP = 20.0    # minimum distance between two peaks


def loudness_envelope(path, *, fps: int = DEFAULT_FPS, window_s: float = DEFAULT_WINDOW_S):
    """Return (envelope, fps): smoothed absolute amplitude over the audio track.

    The track is read at its native rate and aggregated into ``fps`` buckets
    (no resampling of the signal), then smoothed over ``window_s`` seconds.
    """
    from moviepy import AudioFileClip

    audio = AudioFileClip(str(path))
    try:
        samples = audio.to_soundarray(quantize=False)
        duration = float(audio.duration or 0.0)
        native = float(audio.fps or 0.0)
    finally:
        audio.close()
    if samples is None or samples.size == 0:
        raise ValueError(f"no audio track in {path}")
    mono = samples.mean(axis=1) if samples.ndim > 1 else samples
    mono = np.asarray(mono, dtype=np.float32).ravel()

    # Effective sample rate: prefer samples/duration — robust against the
    # resampling MoviePy does when reading (it may not match `audio.fps`).
    rate = (mono.size / duration) if duration > 0 else (native or float(fps))
    block = max(1, int(round(rate / float(fps))))
    n = mono.size // block
    if n < 1:
        env = np.abs(mono)
    else:
        env = np.abs(mono[:n * block]).reshape(n, block).mean(axis=1)
    win = max(1, int(round(window_s * fps)))
    env = np.convolve(env, np.ones(win, dtype=np.float32) / win, mode="same")
    return env, int(fps)


def audio_peaks(path, *, top: int = 10, fps: int = DEFAULT_FPS,
                window_s: float = DEFAULT_WINDOW_S, k: float = DEFAULT_K,
                min_gap: float = DEFAULT_MIN_GAP) -> list[dict]:
    """Loudness peaks as ``[{'t', 'score'}]``, strongest first.

    ``score`` is the envelope value; only peaks above ``mean + k*std`` count.
    """
    env, rate = loudness_envelope(path, fps=fps, window_s=window_s)
    if env.size == 0:
        return []
    std = float(env.std())
    if std <= 0:
        return []
    thr = float(env.mean()) + float(k) * std

    above = env > thr
    peaks: list[dict] = []
    i = 0
    n = len(env)
    while i < n:
        if not above[i]:
            i += 1
            continue
        j = i
        while j < n and above[j]:
            j += 1
        idx = int(i + int(np.argmax(env[i:j])))
        peaks.append({"t": idx / rate, "score": float(env[idx])})
        i = j

    peaks.sort(key=lambda p: p["score"], reverse=True)
    picked: list[dict] = []
    for peak in peaks:
        if len(picked) >= int(top):
            break
        if any(abs(peak["t"] - p["t"]) < float(min_gap) for p in picked):
            continue
        picked.append(peak)
    return sorted(picked, key=lambda p: p["t"])


def _chapter_windows(chapters) -> list[dict]:
    out = []
    for ch in chapters or []:
        try:
            start = float(ch["start_time"])
        except (KeyError, TypeError, ValueError):
            continue
        end = ch.get("end_time")
        title = str(ch.get("title") or "").strip()
        out.append({"start": max(0.0, start), "end": float(end) if end else None,
                    "reason": f"Kapitel: {title}" if title else "Kapitel",
                    "signal": "chapter"})
    return out


def detect(path, *, chapters=None, top: int = 10, lead: float = DEFAULT_LEAD,
           length: float = DEFAULT_LENGTH, min_gap: float = DEFAULT_MIN_GAP,
           k: float = DEFAULT_K, fps: int = DEFAULT_FPS) -> list[dict]:
    """Candidate clip windows from chapters + audio peaks.

    Chapters are kept as-is; audio peaks are added strongest-first, skipping any
    window that overlaps an existing candidate. Returns ``[{start, end, reason,
    signal, score?}]`` sorted by start time.
    """
    candidates = _chapter_windows(chapters)

    def overlaps(start, end):
        for c in candidates:
            c_end = c["end"] if c["end"] is not None else start + length
            if start < c_end and c["start"] < end:
                return True
        return False

    peaks: list[dict] = []
    try:
        peaks = audio_peaks(path, top=top, fps=fps, k=k, min_gap=min_gap)
    except ValueError:
        peaks = []  # no audio track -> chapters only

    added = 0
    for peak in peaks:
        if added >= int(top):
            break
        start = max(0.0, float(peak["t"]) - float(lead))
        end = start + float(length)
        if overlaps(start, end):
            continue
        candidates.append({"start": start, "end": end,
                           "reason": f"Lautheit ({peak['score']:.2f})",
                           "signal": "audio", "score": peak["score"]})
        added += 1

    return sorted(candidates, key=lambda c: c["start"])
