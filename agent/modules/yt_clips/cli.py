"""exec-friendly CLI over the YT-clip art. JSON output.

    python3 -m yt_clips.cli next
    python3 -m yt_clips.cli download --url <url> --out-dir clips --recipe <name> [--subs-lang en]
    python3 -m yt_clips.cli highlights --source 3 --top 10 --add
    python3 -m yt_clips.cli crop-frame --in frames/<bild>.png --box <box> --out sb.png --scale 2
    python3 -m yt_clips.cli format-set --source 3 --regions fmt.json
    python3 -m yt_clips.cli format-set --clip 5 --regions fmt.json
    python3 -m yt_clips.cli format-get --source 3
    python3 -m yt_clips.cli candidates-add --source 3 --json cands.json
    python3 -m yt_clips.cli ocr --clip 5 [--from 320 --to 340 --step 1]
    python3 -m yt_clips.cli candidates-list --source 3 [--status Candidate]
    python3 -m yt_clips.cli clip --clip 5 --out out.mp4 [--size 1080x1920] [--only a,b] [--drop a,b]
    python3 -m yt_clips.cli list

A "format" is the per-video (or per-clip) layout as a ``video_generation`` regions
list, with named regions so they can be selected per clip — see ``skills/ytclip``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from video_generation import edit

from . import crops
from . import download as dl
from . import highlights as hl_k
from . import ocr
from .store import Store


def _dump(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _read_json(src: str):
    if src == "-":
        return json.load(sys.stdin)
    return json.loads(Path(src).read_text(encoding="utf-8"))


def _regions(spec) -> tuple[list, str | None, str | None]:
    """Format spec -> (regions, size, background). Accepts a bare list or dict."""
    if isinstance(spec, list):
        return spec, None, None
    regions = list(spec.get("regions", []))
    if not regions:
        raise ValueError("format has no 'regions' — it needs the layout list "
                         "(the 'boxes' alone are not renderable)")
    return regions, spec.get("size"), spec.get("background")


def _region_rect(region, canvas) -> tuple[float, float, float, float] | None:
    """Resolve the rect a region actually draws on the canvas: (x, y, w, h).

    ``size`` is the target box. For ``fit=contain`` the drawn rect is smaller
    (letterboxed) — it is recomputed from the source box aspect. Returns None
    when the region has no resolvable size.
    """
    if region.get("size") is None:
        return None
    try:
        tw, th = edit.parse_size(region["size"])
    except (TypeError, ValueError):
        return None
    fit = str(region.get("fit", "stretch")).lower()
    if fit == "contain":
        if region.get("box") is None:
            return None
        try:
            _, _, bw, bh = edit.parse_box(region["box"])
        except (TypeError, ValueError):
            return None
        if bw <= 0 or bh <= 0:
            return None
        scale = min(tw / bw, th / bh)
        tw, th = bw * scale, bh * scale
    pos = region.get("position", "center")
    if pos == "center":
        x = (canvas[0] - tw) / 2
        y = (canvas[1] - th) / 2
    elif isinstance(pos, (list, tuple)) and len(pos) == 2:
        x, y = float(pos[0]), float(pos[1])
    else:
        return None
    return x, y, float(tw), float(th)


def _layout_warnings(regions, size=edit.DEFAULT_SIZE, boxes=None) -> list[str]:
    """Cheap geometry + score-box checks for a layout.

    Renders are never blocked — these are warnings meant to catch the usual
    mistakes: gaps that leave black bars, rendering the whole scoreboard instead
    of the ``score`` sub-box, and score bands that are too small or crop digits.
    """
    cw, ch = edit.parse_size(size)
    warnings: list[str] = []
    rects: list[tuple[float, float, float, float]] = []
    names = {str(r.get("name", "")).strip() for r in regions}

    if boxes and boxes.get("score") and "score" not in names:
        warnings.append("format has 'boxes.score' but no region named 'score' — the score value is not shown")
    if boxes and boxes.get("score") and "scoreboard" in names:
        warnings.append("region 'scoreboard' renders the whole board — use the 'score' sub-box (boxes.score)")
    if "score" in names and not (boxes and boxes.get("score")):
        warnings.append("region 'score' has no source box (boxes.score) — later OCR has nothing to crop")

    for i, region in enumerate(regions):
        name = str(region.get("name") or f"region[{i}]")
        if region.get("size") is None:
            warnings.append(f"{name}: no 'size' — renders at source-crop size and likely overflows the canvas")
            continue
        if region.get("position") is None:
            warnings.append(f"{name}: no 'position' — defaults to center")
        fit = str(region.get("fit", "stretch")).lower()
        if fit == "contain":
            warnings.append(f"{name}: fit=contain leaves empty canvas space — use cover for full-bleed")
        elif fit == "stretch":
            warnings.append(f"{name}: fit=stretch distorts — use cover")
        if name == "score" and region.get("box") is not None:
            try:
                _, _, bw, bh = edit.parse_box(region["box"])
                tw, th = edit.parse_size(region["size"])
            except (TypeError, ValueError):
                bw = bh = tw = th = 0
            if bw > 0 and bh > 0 and fit == "cover":
                ratio = (tw / th) / (bw / bh)
                if abs(ratio - 1) > 0.15:
                    warnings.append(
                        f"score: target aspect differs {abs(ratio - 1) * 100:.0f}% from the score box "
                        "— cover crops it; add padding or match the height")
        rect = _region_rect(region, (cw, ch))
        if rect is None:
            warnings.append(f"{name}: cannot resolve box/size")
            continue
        x, y, w, h = rect
        if x < 0 or y < 0 or x + w > cw + 0.5 or y + h > ch + 0.5:
            warnings.append(f"{name}: extends beyond the {cw}x{ch} canvas")
        if name == "score" and h < 100:
            warnings.append(f"score: rendered height {h:.0f}px is too small to read — 200–400px recommended")
        rects.append(rect)
    if not rects:
        return warnings

    # Sample the canvas on a coarse grid; anything not covered is a black bar.
    step = max(1, cw // 108)
    cols, rows = max(1, cw // step), max(1, ch // step)
    uncovered = 0
    for gy in range(rows):
        cy = (gy + 0.5) * step
        for gx in range(cols):
            cx = (gx + 0.5) * step
            if not any(x <= cx <= x + w and y <= cy <= y + h for x, y, w, h in rects):
                uncovered += 1
    pct = 100.0 * uncovered / (cols * rows)
    if pct > 1.0:
        warnings.append(f"layout leaves {pct:.0f}% of the {cw}x{ch} canvas uncovered (black bars)")
    return warnings


MIN_PRE_ROLL = 8.0


def _candidate_windows(items) -> tuple[list[dict], list[str]]:
    """Normalise candidates: plain window, score anchor, or segments (A/B).

    - ``{start, end}`` — one window.
    - ``{score, pre_roll, post_roll}`` — one window around the score **display**.
      The spoken announcement can be far later, so a short pre-roll is flagged.
    - ``{segments: [{start, end}, ...]}`` — several windows concatenated
      (case B: trick + score). ``only``/``drop`` per segment override the
      global region selection.
    """
    out: list[dict] = []
    warnings: list[str] = []
    for item in items:
        row = dict(item)
        segments = row.pop("segments", None)
        if segments:
            segs: list[dict] = []
            for seg in segments:
                try:
                    s, e = float(seg["start"]), float(seg["end"])
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError("each segment needs start/end") from exc
                if e <= s:
                    raise ValueError(f"segment end must be after start ({s}..{e})")
                clean = {"start": s, "end": e}
                for key in ("only", "drop", "reason"):
                    if seg.get(key) is not None:
                        clean[key] = seg[key]
                segs.append(clean)
            if not segs:
                raise ValueError("segments is empty")
            for prev, cur in zip(segs, segs[1:]):
                if cur["start"] < prev["end"]:
                    warnings.append(
                        f"segments overlap at {cur['start']:.1f}s — repeated footage")
            row["segments"] = segs
            row["start"] = min(s["start"] for s in segs)
            row["end"] = max(s["end"] for s in segs)
            row.setdefault("reason", "segments")
        else:
            anchor = row.pop("score", None)
            if anchor is None:
                anchor = row.pop("anchor", None)
            pre = row.pop("pre_roll", None)
            post = row.pop("post_roll", None)
            if anchor is not None:
                pre = 12.0 if pre is None else float(pre)
                post = 3.0 if post is None else float(post)
                row["start"] = max(0.0, float(anchor) - pre)
                row["end"] = float(anchor) + post
                row.setdefault("reason", f"Score @ {float(anchor):.1f}s")
            try:
                start, end = float(row["start"]), float(row["end"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("candidate needs start/end, a score anchor or segments") from exc
            if end <= start:
                raise ValueError(f"clip end must be after start ({start}..{end})")
            if anchor is not None and pre < MIN_PRE_ROLL:
                warnings.append(
                    f"candidate at {start:.1f}s: pre_roll {pre:.0f}s < {MIN_PRE_ROLL:.0f}s "
                    "— likely starts at the celebration, not the trick")
            row["start"], row["end"] = start, end
        if row["end"] - row["start"] < 5.0:
            warnings.append(
                f"candidate at {row['start']:.1f}s: only {row['end'] - row['start']:.1f}s long "
                "— too short for action + reaction")
        out.append(row)
    return out, warnings


def _clip_segments(clip) -> list[dict]:
    """Source windows for a clip row: stored segments, or the single window.

    A row with `segments_json` must have a valid, non-empty list — silently
    falling back to the full start/end span would render a long window instead
    of the intended trick + score composite.
    """
    raw = clip.get("segments_json")
    if raw:
        try:
            segs = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"clip {clip.get('id', '?')}: corrupt segments_json") from exc
        if not isinstance(segs, list) or not segs:
            raise ValueError(f"clip {clip.get('id', '?')}: segments_json is empty or not a list")
        for i, seg in enumerate(segs):
            if "start" not in seg or "end" not in seg:
                raise ValueError(f"clip {clip.get('id', '?')}: segment {i + 1} lacks start/end")
        return segs
    return [{"start": clip["start_s"], "end": clip["end_s"]}]


def _render_segments(src, segments, regions, size, background, out, fps,
                     only=None, drop=None, progress=False) -> str:
    """Render one window, or render each segment and concatenate them (A/B)."""
    if len(segments) == 1:
        seg = segments[0]
        selected = _select_regions(regions, seg.get("only") or only,
                                   seg.get("drop") or drop)
        trimmed = edit.cut(src, float(seg["start"]), float(seg["end"]))
        canvas = edit.layout(trimmed, selected, size, background)
        try:
            return edit.render(canvas, out, fps, progress=progress, label="clip")
        finally:
            canvas.close()

    out_path = Path(out)
    parts: list[Path] = []
    loaded: list = []
    try:
        for i, seg in enumerate(segments):
            selected = _select_regions(regions, seg.get("only") or only,
                                       seg.get("drop") or drop)
            trimmed = edit.cut(src, float(seg["start"]), float(seg["end"]))
            canvas = edit.layout(trimmed, selected, size, background)
            part = out_path.with_name(f"{out_path.stem}.part{i}{out_path.suffix}")
            try:
                edit.render(canvas, part, fps, progress=progress,
                            label=f"part {i + 1}/{len(segments)}")
            finally:
                canvas.close()
            parts.append(part)
        loaded = [edit.load(p) for p in parts]
        merged = edit.concat(loaded)
        try:
            return edit.render(merged, out, fps, progress=progress, label="concat")
        finally:
            merged.close()
    finally:
        for clip in loaded:
            try:
                clip.close()
            except Exception:
                pass
        for part in parts:
            try:
                part.unlink()
            except OSError:
                pass


def _select_regions(regions, only=None, drop=None) -> list:
    """Filter named regions: keep only the ``only`` names, drop the ``drop`` names.

    Unnamed regions are always kept (they aren't selectable). A typo'd/unmatched
    ``--only`` raises instead of silently returning the unnamed base regions.
    """
    def names(value):
        if not value:
            return None
        if isinstance(value, (list, tuple, set)):
            return {str(v).strip() for v in value if str(v).strip()}
        return {s.strip() for s in str(value).split(",") if s.strip()}

    only_set = names(only)
    drop_set = names(drop) or set()
    out: list = []
    matched = False
    for region in regions:
        name = str(region.get("name", "")).strip()
        if name and name in drop_set:
            continue
        if only_set and name:
            if name not in only_set:
                continue
            matched = True
        out.append(region)
    if not out or (only_set and not matched):
        raise ValueError("region selection left nothing — check the --only/--drop names")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="yt_clips")
    p.add_argument("--db", default=None, help="DB path (default: data/brainrot.db)")
    sub = p.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("next", help="what to do next: format | clip | find | download")

    d = sub.add_parser("download", help="download a video via yt-dlp")
    d.add_argument("--url", required=True)
    d.add_argument("--out-dir", default=dl.DEFAULT_OUT_DIR)
    d.add_argument("--recipe", default="", help="recipe name that picked this video")
    d.add_argument("--subs-lang", default=None, help="also fetch the transcript (e.g. 'en')")
    d.add_argument("--overwrite", action="store_true")

    fs = sub.add_parser("format-set", help="store the vision-derived format (source or clip)")
    fs.add_argument("--source", type=int, default=None)
    fs.add_argument("--clip", type=int, default=None, help="per-clip layout (overrides the source)")
    fs.add_argument("--regions", required=True,
                    help="JSON file/'-': regions[] or {regions,boxes,size,background}")

    fg = sub.add_parser("format-get", help="print a source's or clip's format")
    fg.add_argument("--source", type=int, default=None)
    fg.add_argument("--clip", type=int, default=None)

    ca = sub.add_parser("candidates-add", help="add candidate clip windows")
    ca.add_argument("--source", type=int, required=True)
    ca.add_argument("--json", required=True,
                    help="JSON file/'-': [{start,end,reason}], [{score,pre_roll,post_roll,reason}] "
                         "or [{segments:[{start,end}],reason}]")


    cl = sub.add_parser("candidates-list", help="list clips for a source")
    cl.add_argument("--source", type=int, default=None)
    cl.add_argument("--status", default=None, choices=["Candidate", "Used", "Skipped"])

    cp = sub.add_parser("clip", help="render one candidate clip (format + window)")
    cp.add_argument("--clip", type=int, required=True)
    cp.add_argument("--out", required=True)
    cp.add_argument("--size", default=None, help="override output size (default: format)")
    cp.add_argument("--fps", type=int, default=edit.DEFAULT_FPS)
    cp.add_argument("--used", action="store_true", help="mark the clip Used after render")
    cp.add_argument("--progress", action="store_true",
                    help="render progress to stderr (stdout stays JSON)")
    cp.add_argument("--only", default=None, help="comma list: only these named regions")
    cp.add_argument("--drop", default=None, help="comma list: drop these named regions")

    cf = sub.add_parser("crop-frame", help="crop+scale a still frame (2-stage box detection)")
    cf.add_argument("--in", dest="src", required=True)
    cf.add_argument("--out", required=True)
    cf.add_argument("--box", required=True, help="x,y,w,h")
    cf.add_argument("--scale", type=float, default=2.0)
    cf.add_argument("--pad", type=int, default=0)

    oc = sub.add_parser("ocr", help="OCR the fixed score box (values 0.0–10.0)")
    oc.add_argument("--source", type=int, default=None)
    oc.add_argument("--clip", type=int, default=None)
    oc.add_argument("--from", dest="from_s", type=float, default=None)
    oc.add_argument("--to", dest="to_s", type=float, default=None)
    oc.add_argument("--at", default=None, help="comma-separated seconds")
    oc.add_argument("--step", type=float, default=1.0, help="scan step in seconds")
    oc.add_argument("--engine", choices=("auto", "tesseract", "rapidocr"), default="auto")
    oc.add_argument("--pad", type=int, default=6, help="expand the score box (px)")
    oc.add_argument("--scale", type=float, default=3.0, help="upscale before OCR")
    oc.add_argument("--min", type=float, default=0.0)
    oc.add_argument("--max", type=float, default=10.0)
    oc.add_argument("--all", action="store_true", help="include every hit")
    oc.add_argument("--debug-dir", default=None, help="save the score crops")
    oc.add_argument("--max-samples", type=int, default=600)
    sub.add_parser("list", help="sources with candidate/used counts")

    hl = sub.add_parser("highlights", help="auto-detect candidate clips (chapters + audio peaks)")
    hl.add_argument("--source", type=int, required=True)
    hl.add_argument("--top", type=int, default=10)
    hl.add_argument("--add", action="store_true", help="write candidates to the store")
    hl.add_argument("--k", type=float, default=hl_k.DEFAULT_K, help="peak threshold (std multiples)")
    hl.add_argument("--lead", type=float, default=hl_k.DEFAULT_LEAD, help="seconds before the peak")
    hl.add_argument("--length", type=float, default=hl_k.DEFAULT_LENGTH, help="clip length (s)")
    hl.add_argument("--min-gap", type=float, default=hl_k.DEFAULT_MIN_GAP)
    hl.add_argument("--fps", type=int, default=hl_k.DEFAULT_FPS, help="envelope samples/s")

    args = p.parse_args(argv)

    with Store(args.db) as store:
        if args.cmd == "next":
            _dump(store.next_work())
        elif args.cmd == "download":
            got = dl.download(args.url, args.out_dir, overwrite=args.overwrite,
                              subs_lang=args.subs_lang)
            source_id = store.add_source(args.url, ext_id=got.get("id"), path=got["path"],
                                         title=got.get("title", ""),
                                         duration_s=got.get("duration_s"),
                                         recipe=args.recipe,
                                         chapters=got.get("chapters"),
                                         subs_path=got.get("subs"))
            _dump({"source_id": source_id, **got})
        elif args.cmd == "format-set":
            if (args.source is None) == (args.clip is None):
                p.error("format-set needs exactly one of --source or --clip")
            spec = _read_json(args.regions)
            try:
                regions, fmt_size, _ = _regions(spec)
                boxes = spec.get("boxes") if isinstance(spec, dict) else None
                warnings = _layout_warnings(regions, fmt_size or edit.DEFAULT_SIZE, boxes)
            except ValueError as exc:
                p.error(str(exc))
            if args.clip is not None:
                result = store.set_clip_format(args.clip, spec)
            else:
                result = store.set_format(args.source, spec)
            result["warnings"] = warnings
            _dump(result)
        elif args.cmd == "format-get":
            if (args.source is None) == (args.clip is None):
                p.error("format-get needs exactly one of --source or --clip")
            spec = (store.get_clip_format(args.clip) if args.clip is not None
                    else store.get_format(args.source))
            _dump({"source": args.source, "clip": args.clip, "format": spec})
        elif args.cmd == "crop-frame":
            _dump(crops.crop_frame(args.src, edit.parse_box(args.box), args.out,
                                   scale=args.scale, pad=args.pad))
        elif args.cmd == "candidates-add":
            try:
                items, warnings = _candidate_windows(_read_json(args.json))
            except ValueError as exc:
                p.error(str(exc))
            ids = store.add_candidates(args.source, items)
            _dump({"source": args.source, "added": ids, "warnings": warnings})
        elif args.cmd == "ocr":
            if (args.source is None) == (args.clip is None):
                p.error("ocr needs exactly one of --source or --clip")
            clip = store.get_clip(args.clip) if args.clip is not None else None
            source_id = clip["source_id"] if clip else args.source
            source = store.get_source(source_id)
            if not source or not source.get("path"):
                p.error(f"source {source_id} has no local file — download it first")
            spec = ((store.get_clip_format(args.clip) if clip else None)
                    or store.get_format(source_id))
            if spec is None:
                p.error(f"no format for source {source_id} — run format-set first")
            box = (spec.get("boxes") or {}).get("score")
            if not box:
                p.error("format has no boxes.score — the score sub-box is required for OCR")
            if args.at:
                times = [float(x) for x in args.at.replace(" ", "").split(",") if x]
            else:
                start = args.from_s if args.from_s is not None else (
                    clip["start_s"] if clip else None)
                end = args.to_s if args.to_s is not None else (
                    clip["end_s"] if clip else None)
                if start is None or end is None:
                    p.error("ocr needs --from/--to (or --at) for a source; --clip uses its window")
                if end <= start:
                    p.error(f"--to must be after --from ({start}..{end})")
                step = max(0.1, float(args.step))
                times = []
                t = float(start)
                while t <= float(end) + 1e-9:
                    times.append(round(t, 3))
                    t += step
                if len(times) > args.max_samples:
                    times = times[: args.max_samples]
            parsed_box = edit.parse_box(box)
            got = ocr.scan(source["path"], parsed_box, times, engine=args.engine,
                           pad=args.pad, scale=args.scale, lo=args.min,
                           hi=args.max, debug_dir=args.debug_dir,
                           step=args.step if not args.at else 1.0)
            out = {"source": source_id, "clip": args.clip,
                   "box": list(parsed_box), "engine": got["engine"],
                   "checked": got["checked"], "first": got["first"],
                   "first_stable": got["first_stable"], "runs": got["runs"],
                   "empty": got["checked"] - len(got["hits"])}
            if args.all:
                out["hits"] = got["hits"]
            _dump(out)
        elif args.cmd == "candidates-list":
            _dump({"clips": store.list_clips(args.source, args.status)})
        elif args.cmd == "highlights":
            source = store.get_source(args.source)
            if source is None:
                p.error(f"source {args.source} not found")
            if not source.get("path"):
                p.error(f"source {args.source} has no local file — download it first")
            cands = hl_k.detect(source["path"], chapters=store.get_chapters(args.source),
                                top=args.top, lead=args.lead, length=args.length,
                                min_gap=args.min_gap, k=args.k, fps=args.fps)
            out = {"source": args.source, "count": len(cands), "candidates": cands}
            if args.add and cands:
                out["added"] = store.add_candidates(args.source, cands)
            _dump(out)
        elif args.cmd == "list":
            _dump({"sources": store.list_sources()})
        elif args.cmd == "clip":
            clip = store.get_clip(args.clip)
            if clip is None:
                p.error(f"clip {args.clip} not found")
            source = store.get_source(clip["source_id"])
            if not source or not source.get("path"):
                p.error(f"source {clip['source_id']} has no local file — download it first")
            spec = store.get_clip_format(clip["id"]) or store.get_format(clip["source_id"])
            if spec is None:
                p.error(f"no format for clip {clip['id']} or source {clip['source_id']} — run format-set first")
            try:
                regions, fmt_size, fmt_bg = _regions(spec)
            except ValueError as exc:
                p.error(str(exc))
            size = args.size or fmt_size or edit.DEFAULT_SIZE
            boxes = spec.get("boxes") if isinstance(spec, dict) else None
            try:
                segments = _clip_segments(clip)
            except ValueError as exc:
                p.error(str(exc))
            warnings: list[str] = []
            try:
                for i, seg in enumerate(segments):
                    selected = _select_regions(regions, seg.get("only") or args.only,
                                               seg.get("drop") or args.drop)
                    prefix = f"segment {i + 1}: " if len(segments) > 1 else ""
                    warnings.extend(prefix + w
                                    for w in _layout_warnings(selected, size, boxes))
            except ValueError as exc:
                p.error(str(exc))
            src = edit.load(source["path"])
            try:
                out = _render_segments(src, segments, regions, size, fmt_bg,
                                       args.out, args.fps, args.only, args.drop,
                                       progress=args.progress)
            finally:
                src.close()
            result = {"out": out, "clip": clip["id"], "source": source["id"],
                      "start": clip["start_s"], "end": clip["end_s"],
                      "segments": len(segments),
                      "size": list(edit.parse_size(size)), "regions": len(regions),
                      "warnings": warnings}
            if args.used:
                result["clip_row"] = store.mark_clip(clip["id"], "Used")
            _dump(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
