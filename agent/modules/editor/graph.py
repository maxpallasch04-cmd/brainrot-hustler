"""Rezept -> ein ffmpeg-Filtergraph.

Alles in einem Durchlauf: Trim (Input-Seek) -> Crop/Scale je Region ->
Overlay -> Concat (optional mit Übergang). Keine Zwischendateien.
"""

from __future__ import annotations

from .spec import (
    Spec,
    SpecError,
    even,
    parse_box,
    parse_color,
    parse_fit,
    parse_position,
    parse_size,
    parse_time,
)


def _fit_chain(box, size, fit: str, canvas, bg: str) -> str:
    """Quell-Box auf die Zielgröße bringen (`cover` / `contain` / `stretch`)."""
    bx, by, bw, bh = box
    tw, th = size
    W, H = canvas
    crop = f"crop={bw}:{bh}:{bx}:{by}"
    if fit == "cover":
        return (f"{crop},scale={tw}:{th}:force_original_aspect_ratio=increase,"
                f"crop={tw}:{th},setsar=1")
    if fit == "contain":
        return (f"{crop},scale={tw}:{th}:force_original_aspect_ratio=decrease,"
                f"pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2:color={bg},setsar=1")
    return f"{crop},scale={tw}:{th},setsar=1"


def _xy(position, size, canvas) -> tuple[int, int]:
    tw, th = size
    W, H = canvas
    if position == "center":
        return (W - tw) // 2, (H - th) // 2
    return int(position[0]), int(position[1])


def build(rec: Spec, probes: dict[str, dict], *,
          transition: float | None = None) -> dict:
    """Filtergraph + Inputs bauen. `probes` bildet Pfad -> probe()."""
    data = rec.data
    W, H = parse_size(data.get("size", (1080, 1920)))
    W, H = even(W), even(H)
    fps = rec.fps
    bg = parse_color(data.get("background", "#000000"))
    clips = data["clips"]
    if not clips:
        raise SpecError("spec has no clips")

    transition = 0.0 if transition is None else max(0.0, float(transition))

    inputs: list[dict] = []
    filters: list[str] = []
    durations: list[float] = []
    include_audio = True

    # --- Inputs: pro Clip die Quelle (Input-Seek), danach die Bilder ------
    clip_input: list[int] = []
    overlay_input: dict[str, int] = {}

    for clip in clips:
        source = str(clip["source"])
        path = rec.resolve(source)
        info = probes.get(str(path))
        if info is None:
            raise SpecError(f"missing probe for {path}")

        start = parse_time(clip.get("start", 0.0), name="start")
        end = clip.get("end")
        if end is None:
            end = info.get("duration")
        if end is None:
            raise SpecError(f"clip end unknown and source duration missing: {path}")
        end = parse_time(end, name="end")

        clip_input.append(len(inputs))
        inputs.append({
            "path": str(path),
            "ss": start if start > 0 else None,
            "to": end,
            "image": False,
        })
        durations.append(end - start)

        for ov in clip.get("overlays") or []:
            key = str(rec.resolve(str(ov["image"])))
            if key not in overlay_input:
                overlay_input[key] = len(inputs)
                inputs.append({"path": key, "ss": None, "to": None, "image": True})

        if not info.get("has_audio"):
            include_audio = False

    # --- Ein Clip = Fläche + Regionen + Overlays -------------------------
    for i, clip in enumerate(clips):
        idx = clip_input[i]
        dur = durations[i]
        regions = clip.get("regions") or []
        k = len(regions)

        base = f"c{i}b"
        filters.append(
            f"color=c={bg}:s={W}x{H}:r={fps}:d={dur:.3f},format=yuv420p,setsar=1[{base}]"
        )

        src = f"[{idx}:v]"
        pre = f"setpts=PTS-STARTPTS,fps={fps}"
        if k == 0:
            pass  # keine Regionen -> nur Hintergrund (validate warnt)
        elif k == 1:
            filters.append(f"{src}{pre}[r{i}_0]")
        else:
            labels = "".join(f"[r{i}_{j}]" for j in range(k))
            filters.append(f"{src}{pre},split={k}{labels}")

        cur = base
        for j, region in enumerate(regions):
            box = parse_box(region.get("box"))
            size = parse_size(region.get("size", [box[2], box[3]]))
            fit = parse_fit(region.get("fit", "cover"))
            pos = parse_position(region.get("position", [0, 0]))
            x, y = _xy(pos, size, (W, H))

            filters.append(
                f"[r{i}_{j}]" + _fit_chain(box, size, fit, (W, H), bg) + f"[l{i}_{j}]"
            )
            enable = ""
            start = float(region.get("start") or 0.0)
            length = region.get("duration")
            if start > 0 or length is not None:
                end = start + (float(length) if length is not None else dur)
                enable = f":enable='between(t,{start:.3f},{end:.3f})'"

            nxt = f"c{i}o{j}"
            filters.append(
                f"[{cur}][l{i}_{j}]overlay=x={x}:y={y}:eof_action=pass{enable}[{nxt}]"
            )
            cur = nxt

        for j, ov in enumerate(clip.get("overlays") or []):
            image_idx = overlay_input[str(rec.resolve(str(ov["image"])))]
            size = parse_size(ov["size"]) if ov.get("size") is not None else None
            pos = parse_position(ov.get("position", [0, 0]))
            opacity = float(ov.get("opacity", 1.0))
            start = float(ov.get("start") or 0.0)
            length = ov.get("duration")

            chain = []
            if size is not None:
                chain.append(f"scale={size[0]}:{size[1]}")
            chain.append("format=rgba")
            if opacity < 1.0:
                chain.append(f"colorchannelmixer=aa={opacity:.3f}")
            label = f"im{i}_{j}"
            filters.append(f"[{image_idx}:v]{','.join(chain)}[{label}]")

            if size is not None:
                x, y = _xy(pos, size, (W, H))
            elif pos == "center":
                x, y = "(W-w)/2", "(H-h)/2"
            else:
                x, y = int(pos[0]), int(pos[1])

            if length is not None:
                end = start + float(length)
                enable = f":enable='between(t,{start:.3f},{end:.3f})'"
            elif start > 0:
                enable = f":enable='gte(t,{start:.3f})'"
            else:
                enable = ""

            nxt = f"c{i}v{j}"
            filters.append(
                f"[{cur}][{label}]overlay=x={x}:y={y}:eof_action=repeat{enable}[{nxt}]"
            )
            cur = nxt

        filters.append(f"[{cur}]format=yuv420p,setsar=1[v{i}]")

        if include_audio:
            filters.append(
                f"[{idx}:a]asetpts=PTS-STARTPTS,aresample=48000,"
                f"aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}]"
            )

    n = len(clips)
    total = sum(durations)
    if n == 1:
        vout = "v0"
        aout = "a0" if include_audio else None
    elif transition > 0:
        cur = "v0"
        for i in range(1, n):
            offset = sum(durations[:i]) - i * transition
            nxt = f"x{i}"
            filters.append(
                f"[{cur}][v{i}]xfade=transition=fade:duration={transition:.3f}:"
                f"offset={offset:.3f}[{nxt}]"
            )
            cur = nxt
        vout = cur
        total = sum(durations) - (n - 1) * transition

        aout = None
        if include_audio:
            cur = "a0"
            for i in range(1, n):
                nxt = f"xa{i}"
                filters.append(f"[{cur}][a{i}]acrossfade=d={transition:.3f}[{nxt}]")
                cur = nxt
            aout = cur
    else:
        pairs = "".join(
            f"[v{i}]" + (f"[a{i}]" if include_audio else "") for i in range(n)
        )
        filters.append(
            f"{pairs}concat=n={n}:v=1:a={1 if include_audio else 0}[vout]"
            + ("[aout]" if include_audio else "")
        )
        vout = "vout"
        aout = "aout" if include_audio else None

    return {
        "inputs": inputs,
        "filter_complex": ";".join(filters),
        "vout": vout,
        "aout": aout,
        "duration": total,
        "size": [W, H],
        "fps": fps,
    }
