"""exec-friendly CLI over the video editing primitives. JSON output.

Run from the project root:
    python3 -m video_generation.cli <command> [args]

Commands: probe, cut, background, overlay, crop, layout, audio, concat, render.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import edit


def _dump(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _coord(value):
    """x/y args: 'center' stays a string, otherwise -> int."""
    s = str(value)
    return s if s == "center" else int(float(s))


def _render_and_close(clip, out, sources=()):
    path = edit.render(clip, out)
    try:
        clip.close()
    except Exception:
        pass
    for src in sources:
        try:
            src.close()
        except Exception:
            pass
    return path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="video_generation")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("probe", help="print duration/size/fps/audio as JSON")
    pr.add_argument("--in", dest="src", required=True)

    fr = sub.add_parser("frames", help="extract PNG frames from a video")
    fr.add_argument("--in", dest="src", required=True)
    fr.add_argument("--out-dir", default="frames")
    fr.add_argument("--at", default=None, help="comma-separated seconds")
    fr.add_argument("--count", type=int, default=None, help="evenly spaced frames (default 4)")
    fr.add_argument("--width", type=int, default=None, help="downscale width")
    fr.add_argument("--prefix", default=None)

    c = sub.add_parser("cut", help="trim a clip")
    c.add_argument("--in", dest="src", required=True)
    c.add_argument("--start", type=float, default=0.0)
    c.add_argument("--end", type=float, default=None)
    c.add_argument("--out", required=True)

    b = sub.add_parser("background", help="fit a clip onto a 9:16 canvas")
    b.add_argument("--in", dest="src", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--size", default="1080x1920")
    b.add_argument("--bg", default=None, help="colour, image or video path")
    b.add_argument("--margin", type=int, default=0)

    o = sub.add_parser("overlay", help="add an image at (x, y) from T seconds")
    o.add_argument("--in", dest="src", required=True)
    o.add_argument("--out", required=True)
    o.add_argument("--image", required=True)
    o.add_argument("--x", default="0", help="pixels or 'center'")
    o.add_argument("--y", default="0", help="pixels or 'center'")
    o.add_argument("--start", type=float, default=0.0)
    o.add_argument("--duration", type=float, default=None)
    o.add_argument("--size", default=None, help="overlay size WxH")
    o.add_argument("--opacity", type=float, default=1.0)

    cr = sub.add_parser("crop", help="cut a rectangular region out of a clip")
    cr.add_argument("--in", dest="src", required=True)
    cr.add_argument("--out", required=True)
    cr.add_argument("--box", required=True, help="x,y,w,h")
    cr.add_argument("--size", default=None, help="optional target WxH")
    cr.add_argument("--fit", default="stretch", choices=("stretch", "contain", "cover"))

    ly = sub.add_parser("layout", help="compose regions of one clip onto a canvas")
    ly.add_argument("--in", dest="src", required=True)
    ly.add_argument("--out", required=True)
    ly.add_argument("--regions", required=True,
                   help="JSON file with regions[], or '-' for stdin")
    ly.add_argument("--size", default=None)
    ly.add_argument("--background", default=None, help="colour/image/video")
    ly.add_argument("--start", type=float, default=None)
    ly.add_argument("--end", type=float, default=None)

    nz = sub.add_parser("noise", help="add film grain / VHS noise")
    nz.add_argument("--in", dest="src", required=True)
    nz.add_argument("--out", required=True)
    nz.add_argument("--amount", type=float, default=0.06)
    nz.add_argument("--mode", default="grain", choices=list(edit.NOISE_MODES))
    nz.add_argument("--color", action="store_true", help="per-channel colour noise")
    nz.add_argument("--seed", type=int, default=None)

    a = sub.add_parser("audio", help="mix an audio file into the video")
    a.add_argument("--in", dest="src", required=True)
    a.add_argument("--out", required=True)
    a.add_argument("--audio", required=True)
    a.add_argument("--start", type=float, default=0.0)
    a.add_argument("--volume", type=float, default=1.0)
    a.add_argument("--duration", type=float, default=None)

    cc = sub.add_parser("concat", help="join clips end to end")
    cc.add_argument("inputs", nargs="+")
    cc.add_argument("--out", required=True)
    cc.add_argument("--transition", type=float, default=None, help="crossfade seconds")

    r = sub.add_parser("render", help="render a full video from a JSON recipe")
    r.add_argument("--recipe", required=True, help="path to recipe JSON, or '-' for stdin")
    r.add_argument("--out", default=None, help="override the recipe out path")

    args = p.parse_args(argv)

    if args.cmd == "probe":
        _dump(edit.probe(args.src))
    elif args.cmd == "frames":
        times = ([float(x) for x in args.at.replace(" ", "").split(",") if x]
                 if args.at else None)
        got = edit.frames(args.src, times, count=args.count, out_dir=args.out_dir,
                          prefix=args.prefix, width=args.width)
        _dump({"count": len(got), "frames": got})
    elif args.cmd == "cut":
        src = edit.load(args.src)
        out = _render_and_close(edit.cut(src, args.start, args.end), args.out, [src])
        _dump({"out": out})
    elif args.cmd == "background":
        src = edit.load(args.src)
        res = edit.on_background(src, edit.parse_size(args.size), args.bg, args.margin)
        out = _render_and_close(res, args.out, [src])
        _dump({"out": out})
    elif args.cmd == "overlay":
        src = edit.load(args.src)
        size = edit.parse_size(args.size) if args.size else None
        res = edit.overlay(src, args.image, _coord(args.x), _coord(args.y),
                           args.start, args.duration, size, args.opacity)
        out = _render_and_close(res, args.out, [src])
        _dump({"out": out})
    elif args.cmd == "crop":
        src = edit.load(args.src)
        res = edit.crop(src, edit.parse_box(args.box), size=args.size, fit=args.fit)
        out = _render_and_close(res, args.out, [src])
        _dump({"out": out})
    elif args.cmd == "layout":
        if args.regions == "-":
            spec = json.load(sys.stdin)
        else:
            spec = json.loads(Path(args.regions).read_text(encoding="utf-8"))
        if isinstance(spec, dict):
            regions = spec["regions"]
            size = args.size or spec.get("size") or edit.DEFAULT_SIZE
            background = (args.background if args.background is not None
                          else spec.get("background"))
        else:
            regions = spec
            size = args.size or edit.DEFAULT_SIZE
            background = args.background
        src = edit.load(args.src)
        clip = edit.cut(src, args.start or 0.0, args.end) if (args.start or args.end) else src
        res = edit.layout(clip, regions, size, background)
        out = _render_and_close(res, args.out, [src])
        _dump({"out": out, "regions": len(regions),
               "size": list(edit.parse_size(size))})
    elif args.cmd == "noise":
        src = edit.load(args.src)
        res = edit.noise(src, args.amount, args.mode, not args.color, args.seed)
        out = _render_and_close(res, args.out, [src])
        _dump({"out": out})
    elif args.cmd == "audio":
        src = edit.load(args.src)
        res = edit.add_audio(src, args.audio, args.start, args.volume, args.duration)
        out = _render_and_close(res, args.out, [src])
        _dump({"out": out})
    elif args.cmd == "concat":
        sources = [edit.load(path) for path in args.inputs]
        out = _render_and_close(edit.concat(sources, args.transition), args.out, sources)
        _dump({"out": out})
    elif args.cmd == "render":
        if args.recipe == "-":
            recipe = json.load(sys.stdin)
        else:
            recipe = json.loads(Path(args.recipe).read_text(encoding="utf-8"))
        if args.out:
            recipe["out"] = args.out
        _dump(edit.render_recipe(recipe))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
