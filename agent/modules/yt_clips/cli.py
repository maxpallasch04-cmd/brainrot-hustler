"""exec-friendly CLI over the YT-clip art. JSON output.

    python3 -m yt_clips.cli next
    python3 -m yt_clips.cli download --url <url> --out-dir clips --recipe <name> [--subs-lang en]
    python3 -m yt_clips.cli highlights --source 3 --top 10 --add
    python3 -m yt_clips.cli crop-frame --in frames/<bild>.png --box <box> --out sb.png --scale 2
    python3 -m yt_clips.cli format-set --source 3 --regions fmt.json
    python3 -m yt_clips.cli format-set --clip 5 --regions fmt.json
    python3 -m yt_clips.cli format-get --source 3
    python3 -m yt_clips.cli candidates-add --source 3 --json cands.json
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


def _select_regions(regions, only=None, drop=None) -> list:
    """Filter named regions: keep only the ``only`` names, drop the ``drop`` names.

    Unnamed regions are always kept (they aren't selectable). A typo'd/unmatched
    ``--only`` raises instead of silently returning the unnamed base regions.
    """
    only_set = {s.strip() for s in str(only).split(",") if s.strip()} if only else None
    drop_set = {s.strip() for s in str(drop).split(",") if s.strip()} if drop else set()
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
    ca.add_argument("--json", required=True, help="JSON file/'-' with [{start,end,reason}]")

    cl = sub.add_parser("candidates-list", help="list clips for a source")
    cl.add_argument("--source", type=int, default=None)
    cl.add_argument("--status", default=None, choices=["Candidate", "Used", "Skipped"])

    cp = sub.add_parser("clip", help="render one candidate clip (format + window)")
    cp.add_argument("--clip", type=int, required=True)
    cp.add_argument("--out", required=True)
    cp.add_argument("--size", default=None, help="override output size (default: format)")
    cp.add_argument("--fps", type=int, default=edit.DEFAULT_FPS)
    cp.add_argument("--used", action="store_true", help="mark the clip Used after render")
    cp.add_argument("--only", default=None, help="comma list: only these named regions")
    cp.add_argument("--drop", default=None, help="comma list: drop these named regions")

    cf = sub.add_parser("crop-frame", help="crop+scale a still frame (2-stage box detection)")
    cf.add_argument("--in", dest="src", required=True)
    cf.add_argument("--out", required=True)
    cf.add_argument("--box", required=True, help="x,y,w,h")
    cf.add_argument("--scale", type=float, default=2.0)
    cf.add_argument("--pad", type=int, default=0)

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
            if args.clip is not None:
                _dump(store.set_clip_format(args.clip, spec))
            else:
                _dump(store.set_format(args.source, spec))
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
            ids = store.add_candidates(args.source, _read_json(args.json))
            _dump({"source": args.source, "added": ids})
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
                regions = _select_regions(regions, args.only, args.drop)
            except ValueError as exc:
                p.error(str(exc))
            size = args.size or fmt_size or edit.DEFAULT_SIZE
            src = edit.load(source["path"])
            canvas = None
            try:
                trimmed = edit.cut(src, clip["start_s"], clip["end_s"])
                canvas = edit.layout(trimmed, regions, size, fmt_bg)
                out = edit.render(canvas, args.out, args.fps)
            finally:
                if canvas is not None:
                    try:
                        canvas.close()
                    except Exception:
                        pass
                src.close()
            result = {"out": out, "clip": clip["id"], "source": source["id"],
                      "start": clip["start_s"], "end": clip["end_s"],
                      "size": list(edit.parse_size(size)), "regions": len(regions)}
            if args.used:
                result["clip_row"] = store.mark_clip(clip["id"], "Used")
            _dump(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
