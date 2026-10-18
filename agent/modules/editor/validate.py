"""Rezept validieren: generische Invarianten + die Erwartungen des Rezepts.

Der Validator hat keine eigene Meinung zur Aufteilung. Er prüft nur:

* Struktur (Typen, Pflichtfelder, Bereiche)
* harte Invarianten (Region außerhalb des Canvas, Quelle außerhalb des Videos)
* was das Rezept in `expect` verlangt (Overlap, Füllung, Seitenverhältnis)

Ausgabe ist maschinenlesbar: `errors[]` / `warnings[]` mit `code` und `where`.
"""

from __future__ import annotations

from pathlib import Path

from .probe import ProbeError, probe as default_probe
from .spec import (
    DEFAULT_SIZE,
    FITS,
    Spec,
    SpecError,
    coerce,
    even,
    parse_box,
    parse_color,
    parse_fit,
    parse_fps,
    parse_position,
    parse_size,
    parse_time,
)

EXPECT_KEYS = {
    "overlap": ("allow", "forbid"),
    "fill": ("any", "exact"),
    "ratio": ("off", "warn", "error"),
}


def _rect(box):
    x, y, w, h = box
    return x, y, x + w, y + h


def _overlap(a, b) -> bool:
    ax0, ay0, ax1, ay1 = _rect(a)
    bx0, by0, bx1, by1 = _rect(b)
    return ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1


def _inside(inner, outer_w: int, outer_h: int) -> bool:
    x, y, w, h = inner
    return x >= 0 and y >= 0 and x + w <= outer_w and y + h <= outer_h


def _placement(entry: dict, where: str, errors: list, warnings: list):
    """box/size/position/fit eines Region- oder Overlay-Eintrags lesen."""
    out = {}
    try:
        box = parse_box(entry.get("box"))
    except SpecError as exc:
        errors.append({"code": "region.box.invalid", "where": where + ".box",
                       "message": str(exc)})
        return None
    out["box"] = box

    if entry.get("size") is None:
        out["size"] = (box[2], box[3])
    else:
        try:
            out["size"] = parse_size(entry.get("size"))
        except SpecError as exc:
            errors.append({"code": "region.size.invalid", "where": where + ".size",
                           "message": str(exc)})
            return None

    try:
        out["position"] = parse_position(entry.get("position", [0, 0]))
    except SpecError as exc:
        errors.append({"code": "region.position.invalid",
                       "where": where + ".position", "message": str(exc)})
        return None

    try:
        out["fit"] = parse_fit(entry.get("fit", "cover"))
    except SpecError as exc:
        errors.append({"code": "region.fit.invalid", "where": where + ".fit",
                       "message": str(exc)})
        return None

    out["start"] = 0.0
    out["duration"] = None
    if entry.get("start") is not None:
        try:
            out["start"] = parse_time(entry.get("start"), name="start")
        except SpecError as exc:
            errors.append({"code": "region.time.invalid", "where": where + ".start",
                           "message": str(exc)})
    if entry.get("duration") is not None:
        try:
            out["duration"] = parse_time(entry.get("duration"), name="duration")
        except SpecError as exc:
            errors.append({"code": "region.time.invalid",
                           "where": where + ".duration", "message": str(exc)})
    return out


def _covered_area(rects, width: int, height: int) -> int:
    """Von den Rechtecken bedeckte Fläche (Union, Überlappung zählt einmal)."""
    if not rects:
        return 0
    xs = sorted({r[0] for r in rects} | {r[2] for r in rects})
    area = 0
    for i in range(len(xs) - 1):
        x0, x1 = xs[i], xs[i + 1]
        if x1 <= x0:
            continue
        spans = [(r[1], r[3]) for r in rects if r[0] <= x0 and r[2] >= x1]
        if not spans:
            continue
        spans.sort()
        total = 0
        y0, y1 = spans[0]
        for ny0, ny1 in spans[1:]:
            if ny0 > y1:
                total += y1 - y0
                y0, y1 = ny0, ny1
            else:
                y1 = max(y1, ny1)
        total += y1 - y0
        area += total * (x1 - x0)
    return min(area, width * height)


def _fit_effect(bw: int, bh: int, tw: int, th: int, fit: str) -> tuple[str, float]:
    """Was `fit` mit der Quell-Box macht: (art, anteil 0..1)."""
    if not bw or not bh or not tw or not th:
        return fit, 0.0
    if fit == "cover":
        s = max(tw / bw, th / bh)
        visible = (tw / s) * (th / s) / (bw * bh)
        return "cover", max(0.0, 1.0 - min(1.0, visible))
    if fit == "contain":
        s = min(tw / bw, th / bh)
        covered = (bw * s) * (bh * s) / (tw * th)
        return "contain", max(0.0, 1.0 - min(1.0, covered))
    sr, dr = bw / bh, tw / th
    return "stretch", abs(sr / dr - 1.0)


def _expect(spec: Spec, errors: list) -> dict:
    raw = spec.data.get("expect") or {}
    if not isinstance(raw, dict):
        errors.append({"code": "expect.invalid", "where": "expect",
                       "message": "expect must be an object"})
        return {"overlap": "allow", "fill": "any", "ratio": "off"}
    out = {}
    for key, allowed in EXPECT_KEYS.items():
        value = raw.get(key)
        if value is None:
            out[key] = {"overlap": "allow", "fill": "any", "ratio": "off"}[key]
            continue
        value = str(value).lower()
        if value not in allowed:
            errors.append({"code": "expect.invalid", "where": f"expect.{key}",
                           "message": f"{key} must be one of {allowed}, got {value!r}"})
            out[key] = {"overlap": "allow", "fill": "any", "ratio": "off"}[key]
        else:
            out[key] = value
    return out


def validate(spec, *, check_fs: bool = True, probe_fn=None) -> dict:
    """Rezept prüfen. Gibt einen Report zurück, wirft nicht."""
    errors: list[dict] = []
    warnings: list[dict] = []

    def err(code, where, message):
        errors.append({"code": code, "where": where, "message": message})

    def warn(code, where, message):
        warnings.append({"code": code, "where": where, "message": message})

    try:
        rec = coerce(spec)
    except SpecError as exc:
        return {"ok": False, "errors": [{"code": "spec.invalid", "where": "",
                                         "message": str(exc)}],
                "warnings": [], "stats": {}}

    data = rec.data
    expect = _expect(rec, errors)

    try:
        width, height = parse_size(data.get("size", DEFAULT_SIZE))
    except SpecError as exc:
        err("size.invalid", "size", str(exc))
        width, height = DEFAULT_SIZE
    else:
        if width != even(width) or height != even(height):
            warn("size.odd", "size",
                 f"{width}x{height} is not even; render rounds down to "
                 f"{even(width)}x{even(height)}")

    try:
        fps = parse_fps(data.get("fps", 30))
    except SpecError as exc:
        err("fps.invalid", "fps", str(exc))
        fps = 30

    try:
        background = parse_color(data.get("background", "#000000"))
    except SpecError as exc:
        err("background.invalid", "background", str(exc))
        background = "0x000000"

    clips = data.get("clips")
    if not isinstance(clips, list) or not clips:
        err("clips.empty", "clips", "spec needs a non-empty clips list")
        clips = []

    probe_fn = probe_fn or default_probe
    custom_probe = probe_fn is not default_probe
    cache: dict[str, dict | None] = {}
    total_duration = 0.0
    total_regions = 0
    coverages: list[float] = []
    audio_flags: list[bool | None] = []

    for i, clip in enumerate(clips):
        cw = f"clips[{i}]"
        if not isinstance(clip, dict):
            err("clip.invalid", cw, "clip must be an object")
            continue

        source = clip.get("source")
        if not isinstance(source, str) or not source.strip():
            err("clip.source.missing", cw + ".source", "clip needs a source path")
            info = None
            resolved = None
        else:
            resolved = rec.resolve(source)
            if check_fs and not resolved.exists():
                err("clip.source.not_found", cw + ".source",
                    f"file not found: {resolved}")
            key = str(resolved)
            if key not in cache:
                cache[key] = None
                if check_fs or custom_probe:
                    try:
                        cache[key] = probe_fn(resolved)
                    except (ProbeError, OSError) as exc:
                        err("clip.source.unreadable", cw + ".source", str(exc))
            info = cache[key]

        src_w = info["width"] if info else None
        src_h = info["height"] if info else None
        src_duration = None
        if info and info.get("duration"):
            src_duration = float(info["duration"])
        audio_flags.append(info["has_audio"] if info else None)

        start = 0.0
        try:
            start = parse_time(clip.get("start", 0.0), name="start")
        except SpecError as exc:
            err("clip.time.invalid", cw + ".start", str(exc))

        end = None
        if clip.get("end") is not None:
            try:
                end = parse_time(clip.get("end"), name="end")
            except SpecError as exc:
                err("clip.time.invalid", cw + ".end", str(exc))
        elif src_duration is not None:
            end = src_duration

        if end is not None and end <= start:
            err("clip.time.invalid", cw + ".end",
                f"end ({end}) must be greater than start ({start})")
            duration = 0.0
        elif src_duration is not None and start >= src_duration:
            err("clip.time.out_of_range", cw + ".start",
                f"start ({start}) is at/after the source duration ({src_duration})")
            duration = 0.0
        else:
            duration = (end - start) if end is not None else None
            if end is not None and src_duration is not None and end > src_duration + 0.05:
                warn("clip.time.out_of_range", cw + ".end",
                     f"end ({end}) is beyond the source duration ({src_duration})")
        total_duration += duration or 0.0

        regions = clip.get("regions") or []
        if not isinstance(regions, list):
            err("clip.regions.invalid", cw + ".regions", "regions must be a list")
            regions = []
        if not regions:
            warn("clip.regions.empty", cw + ".regions",
                  "clip has no regions; render outputs the background only")

        dests: list[tuple[int, int, int, int]] = []
        seen_names: dict[str, int] = {}
        for j, region in enumerate(regions):
            rw = f"{cw}.regions[{j}]"
            if not isinstance(region, dict):
                err("region.invalid", rw, "region must be an object")
                continue
            total_regions += 1
            name = region.get("name")
            if name is not None:
                key = str(name).strip()
                if not key:
                    warn("region.name.empty", rw + ".name",
                         "name is empty — it is only a label, but empty ones are easy to miss")
                elif key in seen_names:
                    warn("region.name.duplicate", rw + ".name",
                         f"name {key!r} is already used by regions[{seen_names[key]}]")
                else:
                    seen_names[key] = j
            placed = _placement(region, rw, errors, warnings)
            if not placed:
                continue

            bx, by, bw, bh = placed["box"]
            tw, th = placed["size"]
            if src_w is not None and not _inside(placed["box"], src_w, src_h):
                err("region.box.outside_source", rw + ".box",
                    f"box ({bx},{by},{bw},{bh}) is outside the source "
                    f"({src_w}x{src_h})")

            pos = placed["position"]
            x = (width - tw) // 2 if pos == "center" else pos[0]
            y = (height - th) // 2 if pos == "center" else pos[1]
            dest = (x, y, tw, th)
            if not _inside(dest, width, height):
                err("region.outside_canvas", rw + ".position",
                    f"region ({x},{y},{tw},{th}) is outside the canvas "
                    f"({width}x{height})")
            dests.append(dest)

            if bh and th:
                src_ratio = bw / bh
                dst_ratio = tw / th
                mismatch = abs(src_ratio / dst_ratio - 1.0)
                if expect["ratio"] != "off" and mismatch > 0.005:
                    kind, frac = _fit_effect(bw, bh, tw, th, placed["fit"])
                    if kind == "cover":
                        effect = f"cover crops {frac * 100:.1f}% of the source box"
                    elif kind == "contain":
                        effect = f"contain leaves {frac * 100:.1f}% bars"
                    else:
                        effect = f"stretch distorts by {frac * 100:.1f}%"
                    msg = (f"source box {bw}x{bh} ({src_ratio:.3f}) vs destination "
                           f"{tw}x{th} ({dst_ratio:.3f}); {effect}")
                    if expect["ratio"] == "error":
                        err("region.ratio", rw, msg)
                    else:
                        warn("region.ratio", rw, msg)
                elif mismatch > 0.005 and placed["fit"] == "stretch":
                    kind, frac = _fit_effect(bw, bh, tw, th, placed["fit"])
                    warn("region.stretch", rw,
                         f"fit=stretch distorts the source by {frac * 100:.1f}% "
                         f"({bw}x{bh} -> {tw}x{th})")

        if expect["overlap"] == "forbid":
            for a in range(len(dests)):
                for b in range(a + 1, len(dests)):
                    if _overlap(dests[a], dests[b]):
                        err("region.overlap", f"{cw}.regions[{b}]",
                            f"region {b} overlaps region {a} "
                            f"(expect.overlap = {expect['overlap']})")

        if expect["fill"] == "exact":
            covered = _covered_area([_rect(r) for r in dests], width, height)
            canvas = width * height
            if dests and covered != canvas:
                err("canvas.gap", cw,
                    f"regions cover {covered} of {canvas} px "
                    f"({100.0 * covered / canvas:.1f}%); {canvas - covered} px uncovered")
        elif dests:
            covered = _covered_area([_rect(r) for r in dests], width, height)
            canvas = width * height
            if covered < canvas:
                warn("canvas.uncovered", cw,
                     f"regions cover {100.0 * covered / canvas:.1f}% of the canvas; "
                     f"{canvas - covered} px show the background")
            coverages.append(100.0 * covered / canvas)

        overlays = clip.get("overlays") or []
        if not isinstance(overlays, list):
            err("clip.overlays.invalid", cw + ".overlays", "overlays must be a list")
            overlays = []

        for j, ov in enumerate(overlays):
            ow = f"{cw}.overlays[{j}]"
            if not isinstance(ov, dict):
                err("overlay.invalid", ow, "overlay must be an object")
                continue
            image = ov.get("image")
            if not isinstance(image, str) or not image.strip():
                err("overlay.image.missing", ow + ".image", "overlay needs an image path")
            elif check_fs and not rec.resolve(image).exists():
                err("overlay.image.not_found", ow + ".image",
                    f"file not found: {rec.resolve(image)}")

            size = None
            if ov.get("size") is not None:
                try:
                    size = parse_size(ov.get("size"))
                except SpecError as exc:
                    err("overlay.size.invalid", ow + ".size", str(exc))

            try:
                pos = parse_position(ov.get("position", [0, 0]))
            except SpecError as exc:
                err("overlay.position.invalid", ow + ".position", str(exc))
                pos = (0, 0)

            opacity = ov.get("opacity", 1.0)
            if not isinstance(opacity, (int, float)) or isinstance(opacity, bool) \
                    or not (0.0 <= float(opacity) <= 1.0):
                err("overlay.opacity.invalid", ow + ".opacity",
                    "opacity must be a number 0..1")

            start_o = 0.0
            dur_o = None
            try:
                start_o = parse_time(ov.get("start", 0.0), name="start")
                if ov.get("duration") is not None:
                    dur_o = parse_time(ov.get("duration"), name="duration")
            except SpecError as exc:
                err("overlay.time.invalid", ow, str(exc))

            if duration is not None and dur_o is not None and start_o + dur_o > duration + 0.05:
                warn("overlay.time.out_of_range", ow,
                     f"overlay ends at {start_o + dur_o:.2f}s, clip is {duration:.2f}s long")

            if size is not None:
                tw, th = size
                x = (width - tw) // 2 if pos == "center" else pos[0]
                y = (height - th) // 2 if pos == "center" else pos[1]
                if not _inside((x, y, tw, th), width, height):
                    err("overlay.outside_canvas", ow + ".position",
                        f"overlay ({x},{y},{tw},{th}) is outside the canvas "
                        f"({width}x{height})")

    transition = data.get("transition", 0.0)
    try:
        transition = parse_time(transition, name="transition")
    except SpecError as exc:
        err("transition.invalid", "transition", str(exc))
        transition = 0.0
    if transition and len(clips) > 1 and total_duration and \
            transition * (len(clips) - 1) >= total_duration:
        err("transition.too_long", "transition",
            "transitions are longer than the total clip duration")

    if any(flag is False for flag in audio_flags) and any(audio_flags):
        warn("audio.partial", "clips",
             "only some clips have an audio stream; render outputs video without audio")

    report = {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "stats": {
            "clips": len(clips),
            "regions": total_regions,
            "size": [width, height],
            "fps": fps,
            "background": background,
            "transition": transition,
            "duration": round(total_duration, 3) if total_duration else None,
            "coverage": round(min(coverages), 1) if coverages else None,
        },
    }
    return report
