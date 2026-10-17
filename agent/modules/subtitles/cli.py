"""exec-friendly CLI over the subtitle layer. JSON output.

    python3 -m subtitles.cli info --in transcript.vtt
    python3 -m subtitles.cli cut  --in transcript.vtt --start 1200 --end 1220 --out clip.srt
    python3 -m subtitles.cli burn --in clip.mp4 --subs clip.srt --out out.mp4 \
        --font-size 64 --margin-v 220 --outline 3

Subtitles stay a separate artifact — ``cut`` needs no video, ``burn`` is the pure
``video + subtitles -> video`` step.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import subs


def _dump(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="subtitles")
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("info", help="cue count + duration of a subtitle file")
    i.add_argument("--in", dest="src", required=True)

    c = sub.add_parser("cut", help="cut a clip-relative window out of a transcript")
    c.add_argument("--in", dest="src", required=True, help=".vtt or .srt")
    c.add_argument("--start", type=float, required=True)
    c.add_argument("--end", type=float, default=None)
    c.add_argument("--out", required=True, help="output .srt")
    c.add_argument("--no-offset", action="store_true",
                   help="keep absolute timestamps (default: shift to clip-relative)")
    c.add_argument("--no-clean", action="store_true", help="keep rolling duplicates")
    c.add_argument("--snap", choices=("sentence", "word"), default=None,
                   help="snap start/end outward to the nearest boundary")
    c.add_argument("--pause", type=float, default=0.6,
                   help="pause in seconds that ends a sentence (default 0.6)")
    c.add_argument("--text", action="store_true",
                   help="include the clip text (short, for titles)")

    b = sub.add_parser("burn", help="hardsub a video (ffmpeg + libass)")
    b.add_argument("--in", dest="src", required=True, help="video")
    b.add_argument("--subs", required=True, help="subtitle file (.srt/.vtt)")
    b.add_argument("--out", required=True)
    b.add_argument("--style", default=None, help="raw force_style override")
    b.add_argument("--font", default=None)
    b.add_argument("--font-size", type=int, default=None)
    b.add_argument("--outline", type=int, default=None)
    b.add_argument("--alignment", type=int, default=None, help="ASS alignment (2 = bottom center)")
    b.add_argument("--margin-v", type=int, default=None, help="bottom margin in px")
    b.add_argument("--crf", type=int, default=20)
    b.add_argument("--preset", default="medium")

    n = sub.add_parser("numbers", help="score-like numbers in a transcript (cut anchors)")
    n.add_argument("--in", dest="src", required=True, help=".vtt or .srt")
    n.add_argument("--min", type=float, default=None, help="keep values above this")
    n.add_argument("--max", type=float, default=None, help="keep values below this")

    w = sub.add_parser("words", help="word timings around one time (small window)")
    w.add_argument("--in", dest="src", required=True, help=".vtt or .srt")
    w.add_argument("--at", type=float, required=True)
    w.add_argument("--window", type=float, default=3.0, help="seconds before/after")
    w.add_argument("--limit", type=int, default=60, help="max words returned")

    s = sub.add_parser("snap", help="nearest word/sentence boundary")
    s.add_argument("--in", dest="src", required=True, help=".vtt or .srt")
    s.add_argument("--at", type=float, required=True)
    s.add_argument("--mode", choices=("sentence", "word"), default="sentence")
    s.add_argument("--direction", choices=("before", "after", "nearest"),
                   default="nearest")
    s.add_argument("--pause", type=float, default=0.6)

    args = p.parse_args(argv)

    if args.cmd == "info":
        cues = subs.load(args.src)
        last = max((c["end"] for c in cues), default=0.0)
        _dump({"path": args.src, "cues": len(cues), "last_end": round(last, 3)})
    elif args.cmd == "cut":
        cues = subs.load(args.src)
        if not args.no_clean:
            cues = subs.dedupe(cues)
        start, end = args.start, args.end
        snapped = None
        if args.snap:
            word_list = subs.words(cues)
            s = subs.snap(start, word_list, mode=args.snap, direction="before",
                          pause=args.pause)
            if s["text"] is not None:
                start = s["snapped"]
            if end is not None:
                e = subs.snap(end, word_list, mode=args.snap, direction="after",
                              pause=args.pause)
                if e["text"] is not None:
                    end = e["snapped"]
            snapped = {"start": start, "end": end}
        window = subs.window(cues, start, end, offset=not args.no_offset)
        if not window:
            raise SystemExit(f"no cues in {start}..{end}")
        path = subs.write_srt(window, args.out)
        out = {"out": path, "cues": len(window), "start": start, "end": end,
               "offset": not args.no_offset}
        if snapped:
            out["requested"] = {"start": args.start, "end": args.end}
            out["snapped"] = snapped
        if args.text:
            out["text"] = " ".join(c["text"] for c in window)[:400]
        _dump(out)
    elif args.cmd == "burn":
        style = args.style or subs.build_style(
            font=args.font, font_size=args.font_size, outline=args.outline,
            alignment=args.alignment, margin_v=args.margin_v)
        out = subs.burn(args.src, args.subs, args.out, force_style=style,
                        crf=args.crf, preset=args.preset)
        _dump({"out": out, "subs": args.subs, "style": style})
    elif args.cmd == "numbers":
        hits = subs.find_numbers(subs.load(args.src), lo=args.min, hi=args.max)
        _dump({"path": args.src, "count": len(hits), "hits": hits})
    elif args.cmd == "words":
        cues = subs.dedupe(subs.load(args.src))
        word_list = subs.words(cues)
        selected = subs.window_words(word_list, args.at, seconds=args.window,
                                     limit=args.limit)
        _dump({"at": args.at, "window": args.window, "count": len(selected),
               "approx": any(w.get("approx") for w in selected),
               "words": selected})
    elif args.cmd == "snap":
        cues = subs.dedupe(subs.load(args.src))
        _dump(subs.snap(args.at, subs.words(cues), mode=args.mode,
                        direction=args.direction, pause=args.pause))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
