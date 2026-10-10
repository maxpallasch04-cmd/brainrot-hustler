"""Video editing primitives for BrainrotHustler (MoviePy 2.x).

Pure functions over MoviePy clips: cut, fit on a background, overlay images
at (x, y, t), mix audio in, and concatenate. `render_recipe` drives the whole
pipeline from a plain dict (see README).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import ImageColor
from moviepy import (
    AudioFileClip,
    ColorClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
    concatenate_videoclips,
)
from moviepy.video.fx import Loop

DEFAULT_SIZE = (1080, 1920)  # 9:16
DEFAULT_FPS = 30
MIN_SIZE = (720, 1280)       # spec: at least 720p


# ---- helpers ------------------------------------------------------------

def _even(n: float) -> int:
    """Round to the nearest even int (H.264 wants even dimensions)."""
    n = int(round(n))
    return n if n % 2 == 0 else n + 1


def parse_size(value) -> tuple[int, int]:
    """Accept (w, h), '1080x1920' or '1080,1920' -> (w, h)."""
    if isinstance(value, (list, tuple)):
        return int(value[0]), int(value[1])
    w, _, h = str(value).lower().replace(",", "x").partition("x")
    return int(w), int(h)


def parse_color(value) -> tuple[int, int, int]:
    """'#000000', 'black' or [r, g, b] -> (r, g, b)."""
    if isinstance(value, (list, tuple)):
        return tuple(int(c) for c in value)[:3]
    return ImageColor.getrgb(str(value))


def _xy(x, y, canvas, obj) -> tuple[float, float]:
    """Resolve an (x, y) top-left position; 'center' is allowed per axis."""
    cw, ch = canvas
    ow, oh = obj
    px = cw / 2 - ow / 2 if x == "center" else x
    py = ch / 2 - oh / 2 if y == "center" else y
    return px, py


# ---- load / probe -------------------------------------------------------

def load(path) -> VideoFileClip:
    """Open a video file as a clip (remember to close it)."""
    return VideoFileClip(str(path))


def load_audio(path) -> AudioFileClip:
    """Open an audio file as a clip (remember to close it)."""
    return AudioFileClip(str(path))


def probe(path) -> dict:
    """Basic facts about a media file: duration, size, fps, audio."""
    clip = VideoFileClip(str(path))
    try:
        return {
            "path": str(path),
            "duration": round(clip.duration, 3),
            "size": list(clip.size),
            "fps": clip.fps,
            "has_audio": clip.audio is not None,
        }
    finally:
        clip.close()


# ---- core operations ----------------------------------------------------

def cut(clip, start: float = 0.0, end: float | None = None):
    """Trim a clip to [start, end) seconds."""
    return clip.subclipped(float(start), None if end is None else float(end))


def contain(clip, size=DEFAULT_SIZE):
    """Scale to fit fully inside `size`, keeping the aspect ratio."""
    w, h = parse_size(size)
    scale = min(w / clip.w, h / clip.h)
    return clip.resized(new_size=(_even(clip.w * scale), _even(clip.h * scale)))


def cover(clip, size=DEFAULT_SIZE):
    """Scale to fill `size` (keeping aspect), then center-crop."""
    w, h = parse_size(size)
    scale = max(w / clip.w, h / clip.h)
    big = clip.resized(new_size=(_even(clip.w * scale), _even(clip.h * scale)))
    return big.cropped(x_center=big.w / 2, y_center=big.h / 2, width=w, height=h)


def _background(spec, size, duration):
    """Build a full-canvas background clip from a colour / image / video spec."""
    w, h = parse_size(size)
    if spec is None:
        return ColorClip(size=(w, h), color=(0, 0, 0), duration=duration)

    if isinstance(spec, (list, tuple)):
        return ColorClip(size=(w, h), color=parse_color(spec), duration=duration)

    spec = str(spec)
    if not Path(spec).exists():  # a colour like '#111' or 'black'
        return ColorClip(size=(w, h), color=parse_color(spec), duration=duration)

    if Path(spec).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
        bg = ImageClip(spec).with_duration(duration)
    else:
        bg = VideoFileClip(spec).without_audio()

    bg = cover(bg, (w, h))
    if bg.duration is None or bg.duration < duration:
        bg = bg.with_effects([Loop(duration=duration)])
    else:
        bg = bg.subclipped(0, duration)
    return bg


def on_background(clip, size=DEFAULT_SIZE, background=None, margin: int = 0,
                  position="center"):
    """Place `clip` (scaled to fit) on a 9:16 canvas.

    `background`: None -> black, a colour ('#111' / 'black' / [r,g,b]),
    or a path to an image/video used as the backdrop.
    `position`: 'center' or an (x, y) top-left tuple.
    """
    w, h = parse_size(size)
    duration = clip.duration
    bg = _background(background, (w, h), duration)
    inner = (w - 2 * margin, h - 2 * margin) if margin else (w, h)
    fg = contain(clip, inner)
    if position == "center":
        pos = _xy("center", "center", (w, h), fg.size)
    else:
        pos = tuple(position)
    return CompositeVideoClip([bg, fg.with_position(pos)], size=(w, h))


def overlay(video, image, x=0, y=0, start: float = 0.0, duration: float | None = None,
            size=None, opacity: float = 1.0):
    """Overlay an image (path or ImageClip) at (x, y) from `start` for `duration`.

    `x`/`y` may be pixel ints or 'center'. `size` is an optional 'WxH' target.
    """
    ov = ImageClip(str(image)) if isinstance(image, (str, Path)) else image
    if size is not None:
        ov = ov.resized(new_size=parse_size(size))
    if duration is None:
        duration = max(0.05, video.duration - float(start))
    ov = ov.with_start(float(start)).with_duration(float(duration))
    if opacity != 1.0:
        ov = ov.with_opacity(float(opacity))
    return CompositeVideoClip([video, ov.with_position(_xy(x, y, video.size, ov.size))],
                              size=video.size)


# ---- stylise ------------------------------------------------------------

NOISE_MODES = ("grain", "vhs")


def noise(clip, amount: float = 0.06, mode: str = "grain",
          monochrome: bool = True, seed: int | None = None):
    """Add film grain / VHS noise to a clip (fresh, random on every frame).

    `amount`: noise strength as a fraction of full scale (0 = off, ~0.1 = heavy).
    `mode`:   'grain' (plain noise) or 'vhs' (noise + scanline darkening).
    `monochrome`: True -> grey noise, False -> per-channel colour noise.
    `seed`:   optional int for reproducible noise.
    """
    if mode not in NOISE_MODES:
        raise ValueError(f"mode must be one of {NOISE_MODES}, got {mode!r}")
    rng = np.random.default_rng(seed)

    def apply(frame):
        f = frame.astype(np.float32)
        h, w = frame.shape[:2]
        channels = 1 if (monochrome or frame.ndim == 2) else frame.shape[2]
        n = rng.normal(0.0, 255.0 * float(amount), size=(h, w, channels))
        if channels == 1 and frame.ndim == 3:
            n = np.repeat(n, frame.shape[2], axis=2)
        out = f + n
        if mode == "vhs":
            scan = np.ones((h, 1, 1), dtype=np.float32)
            scan[::2] = 0.86  # darken every other line
            out = out * scan
        return np.clip(out, 0, 255).astype(np.uint8)

    return clip.image_transform(apply)


def _noise_from_spec(clip, spec):
    """`noise` recipe spec -> applied clip. Accepts true / number / dict."""
    if spec is True:
        spec = {}
    if isinstance(spec, (int, float)):
        spec = {"amount": float(spec)}
    if not isinstance(spec, dict):
        raise ValueError("noise spec must be true, a number or a dict")
    return noise(clip, amount=spec.get("amount", 0.06),
                 mode=spec.get("mode", "grain"),
                 monochrome=spec.get("monochrome", True),
                 seed=spec.get("seed"))


def add_audio(video, audio, start: float = 0.0, volume: float = 1.0,
              duration: float | None = None):
    """Mix an audio file (or clip) into the video, starting at `start` seconds."""
    a = AudioFileClip(str(audio)) if isinstance(audio, (str, Path)) else audio
    if duration is not None:
        a = a.subclipped(0, float(duration))
    a = a.with_start(float(start)).with_volume_scaled(float(volume))
    base = video.audio
    return video.with_audio(CompositeAudioClip([base, a]) if base is not None else a)


def concat(clips, transition: float | None = None):
    """Concatenate clips end to end. Same-size clips use a lossless 'chain'."""
    clips = list(clips)
    if not clips:
        raise ValueError("concat needs at least one clip")
    method = "chain" if len({tuple(c.size) for c in clips}) == 1 else "compose"
    return concatenate_videoclips(clips, method=method, transition=transition,
                                 padding=-(transition or 0))


# ---- render -------------------------------------------------------------

def render(clip, out, fps: int = DEFAULT_FPS, verbose: bool = False) -> str:
    """Write `clip` to `out` as H.264/AAC mp4. Returns the output path."""
    out = str(out)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    clip.write_videofile(out, fps=int(fps), codec="libx264", audio_codec="aac",
                         preset="medium", logger="bar" if verbose else None)
    return out


def _size_warning(size) -> str | None:
    _, h = parse_size(size)
    if h < MIN_SIZE[1]:
        return f"output height {h}px is below the {MIN_SIZE[1]}px (720p) minimum"
    return None


def render_recipe(recipe: dict) -> dict:
    """Build and render a full video from a plain dict. See README.

    Top level: size, fps, background, noise, audio[], clips[], out.
    Each clip: source, start, end, background, margin, overlays[], noise, audio[].
    """
    size = parse_size(recipe.get("size", DEFAULT_SIZE))
    fps = int(recipe.get("fps", DEFAULT_FPS))
    out = recipe.get("out") or recipe.get("output")
    if not out:
        raise ValueError("recipe needs an 'out' path")
    default_bg = recipe.get("background")

    sources: list = []
    rendered = None
    try:
        clips = []
        for spec in recipe.get("clips", []):
            src = VideoFileClip(str(spec["source"]))
            sources.append(src)
            clip = src
            if spec.get("start") is not None or spec.get("end") is not None:
                clip = cut(clip, spec.get("start", 0), spec.get("end"))
            clip = on_background(clip, size, spec.get("background", default_bg),
                                 margin=int(spec.get("margin", 0)))
            for ov in spec.get("overlays", []):
                clip = overlay(clip, ov["image"], ov.get("x", 0), ov.get("y", 0),
                               ov.get("start", 0.0), ov.get("duration"),
                               ov.get("size"), ov.get("opacity", 1.0))
            if spec.get("noise"):
                clip = _noise_from_spec(clip, spec["noise"])
            for au in spec.get("audio", []):
                clip = add_audio(clip, au["source"], au.get("start", 0.0),
                                 au.get("volume", 1.0), au.get("duration"))
            clips.append(clip)
        if not clips:
            raise ValueError("recipe has no clips")

        rendered = concat(clips) if len(clips) > 1 else clips[0]
        if recipe.get("noise"):
            rendered = _noise_from_spec(rendered, recipe["noise"])
        for au in recipe.get("audio", []):  # whole-video track
            rendered = add_audio(rendered, au["source"], au.get("start", 0.0),
                                 au.get("volume", 1.0), au.get("duration"))

        path = render(rendered, out, fps)
        return {"out": path, "size": list(size), "fps": fps,
                "duration": round(rendered.duration, 3),
                "warning": _size_warning(size)}
    finally:
        if rendered is not None:
            try:
                rendered.close()
            except Exception:
                pass
        for clip in sources:
            try:
                clip.close()
            except Exception:
                pass
