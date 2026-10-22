"""exec-friendly CLI over the YT-clip art. JSON output.

    python3 -m yt_clips.cli next
    python3 -m yt_clips.cli request --url <url> --recipe <name>
    python3 -m yt_clips.cli fetch --source <id> --url <bucket-url> [--no-transcribe]
    python3 -m yt_clips.cli transcribe --source <id> [--model base] [--lang en]
    python3 -m yt_clips.cli highlights --source 3 --top 10 --add
    python3 -m yt_clips.cli crop-frame --in frames/<bild>.png --box <box> --out sb.png --scale 2
    python3 -m yt_clips.cli candidates-add --source 3 --json cands.json
    python3 -m yt_clips.cli motion --clip 5 [--fps 4 --width 160]
    python3 -m yt_clips.cli motion --source 3 --from 300 --to 360
    python3 -m yt_clips.cli ocr --clip 5 --box 1200,80,180,90 [--from 320 --to 340 --step 1]
    python3 -m yt_clips.cli boxes-set --source 3 --json boxes.json
    python3 -m yt_clips.cli boxes-get --source 3
    python3 -m yt_clips.cli candidates-list --source 3 [--status Candidate]
    python3 -m yt_clips.cli used --clip 5 [--video-id 12]
    python3 -m yt_clips.cli skip --clip 5
    python3 -m yt_clips.cli list

This module is **state + analysis**: sources, candidates, status, OCR, motion,
highlights, crops. It does not render and it does not know about layouts.

Rendering is `editor`: the agent builds a recipe JSON (regions + clips) and runs
`editor.cli validate/render`. The recipe is the layout artifact, not this store.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import brainrot_paths as paths
from hosting import DownloadError, download as http_download

from . import crops
from . import highlights as hl_k
from . import motion
from . import ocr
from . import urls
from .store import Store


def _dump(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _read_json(src: str):
    if src == "-":
        return json.load(sys.stdin)
    return json.loads(Path(src).read_text(encoding="utf-8"))


def _parse_box(value) -> tuple[int, int, int, int]:
    """`"x,y,w,h"` oder `[x,y,w,h]` -> Tupel."""
    parts = value.split(",") if isinstance(value, str) else list(value)
    if len(parts) != 4:
        raise ValueError("box needs four values: x,y,w,h")
    try:
        x, y, w, h = (int(float(p)) for p in parts)
    except (TypeError, ValueError) as exc:
        raise ValueError("box values must be numbers: x,y,w,h") from exc
    if w <= 0 or h <= 0:
        raise ValueError("box width/height must be positive")
    return x, y, w, h


MIN_PRE_ROLL = 8.0

#: Was der Operator hochladen darf. Alles andere wird trotzdem genommen, aber
#: als MP4 benannt - der Editor probiert ffmpeg und scheitert sonst erst später.
VIDEO_SUFFIXES = (".mp4", ".mkv", ".webm", ".mov", ".m4v")

REQUEST_MESSAGE = (
    "Bitte herunterladen ({quality}p, mp4) und in den Bucket legen, dann den "
    "Link zurückschicken:\n{url}\n"
    "Transkript erzeuge ich selbst - keine Untertitel nötig."
)


def _video_suffix(url: str) -> str:
    """Dateiendung aus der URL, sonst ``.mp4``."""
    suffix = Path(unquote(urlparse(str(url)).path)).suffix.lower()
    return suffix if suffix in VIDEO_SUFFIXES else ".mp4"


def _run_transcribe(path, out, *, model=None, lang=None, threads=0) -> dict:
    """Lokales Transkript über ``editor.subtitles`` (faster-whisper)."""
    from editor import subtitles as subs_mod

    return subs_mod.transcribe(
        path, out, model=model or os.environ.get("WHISPER_MODEL") or "base",
        lang=lang, threads=threads)


def _candidate_windows(items) -> tuple[list[dict], list[str]]:
    """Normalise candidates: plain window, score anchor, or segments (A/B).

    - ``{start, end}`` — one window.
    - ``{score, pre_roll, post_roll}`` — one window around the score **display**.
      The spoken announcement can be far later, so a short pre-roll is flagged.
    - ``{segments: [{start, end}, ...]}`` — several windows that belong together
      (case B: trick + score). They are stored as a proposal; how they are cut
      and joined is decided in the recipe.
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
                if seg.get("reason") is not None:
                    clean["reason"] = seg["reason"]
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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="yt_clips")
    p.add_argument("--db", default=None, help="DB path (default: memory/brainrot.db)")
    sub = p.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("next", help="what to do next for one recipe: clip | find | await_upload | request_upload")
    n.add_argument("--recipe", required=True,
                   help="recipe name — the queue key (sources of other recipes are ignored)")

    rq = sub.add_parser("request", help="Video beim Operator anfordern (er lädt + hostet)")
    rq.add_argument("--url", required=True)
    rq.add_argument("--recipe", required=True, help="recipe name that picked this video")
    rq.add_argument("--note", default=None, help="optionaler Zusatz für die Nachricht")

    fe = sub.add_parser("fetch", help="gelieferte Datei aus dem Bucket lokal ablegen")
    fe.add_argument("--source", type=int, required=True)
    fe.add_argument("--url", required=True, help="direkter http(s)-Link zur Datei")
    fe.add_argument("--out-dir", default=None,
                    help="Zielordner (default: memory/<channel>/clips)")
    fe.add_argument("--title", default=None, help="Titel überschreiben")
    fe.add_argument("--overwrite", action="store_true")
    fe.add_argument("--no-transcribe", action="store_true",
                    help="kein lokales Transkript erzeugen")
    fe.add_argument("--model", default=None,
                    help="Whisper-Modell (Default: $WHISPER_MODEL oder 'base')")
    fe.add_argument("--lang", default=None, help="Sprache, z. B. en (Default: auto)")
    fe.add_argument("--threads", type=int, default=0, help="Whisper-CPU-Threads")

    tr = sub.add_parser("transcribe", help="Transkript für eine geladene Quelle erzeugen")
    tr.add_argument("--source", type=int, required=True)
    tr.add_argument("--out", default=None, help="Ziel (.vtt); Default: neben dem Video")
    tr.add_argument("--model", default=None,
                    help="Whisper-Modell (Default: $WHISPER_MODEL oder 'base')")
    tr.add_argument("--lang", default=None, help="Sprache, z. B. en (Default: auto)")
    tr.add_argument("--threads", type=int, default=0)

    ca = sub.add_parser("candidates-add", help="add candidate clip windows")
    ca.add_argument("--source", type=int, required=True)
    ca.add_argument("--json", required=True,
                    help="JSON file/'-': [{start,end,reason}], [{score,pre_roll,post_roll,reason}] "
                         "or [{segments:[{start,end}],reason}]")

    cl = sub.add_parser("candidates-list", help="list clips for a source")
    cl.add_argument("--source", type=int, default=None)
    cl.add_argument("--status", default=None, choices=["Candidate", "Used", "Skipped"])

    bs = sub.add_parser("boxes-set", help="store the measured sub-boxes of a source")
    bs.add_argument("--source", type=int, required=True)
    bs.add_argument("--json", required=True,
                    help="JSON file/'-': {name: [x,y,w,h]}, e.g. {\"score\": [1200,80,180,90]}")

    bg = sub.add_parser("boxes-get", help="print a source's sub-boxes")
    bg.add_argument("--source", type=int, required=True)

    rs = sub.add_parser("recipe-set", help="tag an existing source with its recipe")
    rs.add_argument("--source", type=int, required=True)
    rs.add_argument("--recipe", required=True)

    cf = sub.add_parser("crop-frame", help="crop+scale a still frame (2-stage box detection)")
    cf.add_argument("--in", dest="src", required=True)
    cf.add_argument("--out", required=True)
    cf.add_argument("--box", required=True, help="x,y,w,h")
    cf.add_argument("--scale", type=float, default=2.0)
    cf.add_argument("--pad", type=int, default=0)

    mo = sub.add_parser("motion", help="measure movement over a window (clip start anchor)")
    mo.add_argument("--source", type=int, default=None)
    mo.add_argument("--clip", type=int, default=None)
    mo.add_argument("--from", dest="from_s", type=float, default=None)
    mo.add_argument("--to", dest="to_s", type=float, default=None)
    mo.add_argument("--fps", type=float, default=motion.DEFAULT_FPS,
                    help="samples per second (default 4)")
    mo.add_argument("--width", type=int, default=motion.DEFAULT_WIDTH,
                    help="downscale width before diffing (default 160)")
    mo.add_argument("--threshold", type=float, default=None,
                    help="mean pixel-change threshold 0..1 (default: adaptive, floor 0.005)")

    oc = sub.add_parser("ocr", help="OCR a fixed score box (values 0.0–10.0)")
    oc.add_argument("--source", type=int, default=None)
    oc.add_argument("--clip", type=int, default=None)
    oc.add_argument("--box", required=True, help="score box in source pixels: x,y,w,h")
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

    ls = sub.add_parser("list", help="sources with candidate/used counts")
    ls.add_argument("--recipe", default=None, help="only sources of this recipe")

    hl = sub.add_parser("highlights", help="auto-detect candidate clips (chapters + audio peaks)")
    hl.add_argument("--source", type=int, required=True)
    hl.add_argument("--top", type=int, default=10)
    hl.add_argument("--add", action="store_true", help="write candidates to the store")
    hl.add_argument("--k", type=float, default=hl_k.DEFAULT_K, help="peak threshold (std multiples)")
    hl.add_argument("--lead", type=float, default=hl_k.DEFAULT_LEAD, help="seconds before the peak")
    hl.add_argument("--length", type=float, default=hl_k.DEFAULT_LENGTH, help="clip length (s)")
    hl.add_argument("--min-gap", type=float, default=hl_k.DEFAULT_MIN_GAP)
    hl.add_argument("--fps", type=int, default=hl_k.DEFAULT_FPS, help="envelope samples/s")

    us = sub.add_parser("used", help="mark a clip as Used")
    us.add_argument("--clip", type=int, required=True)
    us.add_argument("--video-id", type=int, default=None,
                    help="id of the uploaded/published video")

    sk = sub.add_parser("skip", help="mark a clip as Skipped")
    sk.add_argument("--clip", type=int, required=True)

    ex = sub.add_parser("exhaust", help="Quelle als fertig markieren (kein find mehr)")
    ex.add_argument("--source", type=int, required=True)

    ro = sub.add_parser("reopen", help="Exhausted zurücknehmen")
    ro.add_argument("--source", type=int, required=True)

    args = p.parse_args(argv)
    channel = paths.channel(required=True)

    with Store(args.db, channel=channel) as store:
        if args.cmd == "next":
            _dump(store.next_work(args.recipe))
        elif args.cmd == "request":
            vid = urls.youtube_id(args.url)
            source_id = store.add_source(
                args.url, ext_id=vid, recipe=args.recipe,
                status="AwaitingUpload")
            _dump({
                "action": "request_upload",
                "source_id": source_id,
                "video_id": vid,
                "url": args.url,
                "operator_message": REQUEST_MESSAGE.format(
                    quality=1080, url=args.url),
                "note": args.note,
                "next": (f"yt_clips.cli fetch --source {source_id} "
                         "--url <bucket-url>"),
            })
        elif args.cmd == "fetch":
            source = store.get_source(args.source)
            if source is None:
                p.error(f"source {args.source} not found")
            out_dir = Path(args.out_dir or paths.channel_dir("clips"))
            out_dir.mkdir(parents=True, exist_ok=True)
            stem = source.get("ext_id") or f"source{args.source}"
            dest = out_dir / f"{stem}{_video_suffix(args.url)}"
            try:
                if dest.exists() and not args.overwrite:
                    got = {"path": str(dest), "filename": dest.name,
                           "bytes": dest.stat().st_size, "url": args.url,
                           "cached": True}
                else:
                    got = http_download(args.url, dest=str(dest),
                                        max_bytes=None)
            except DownloadError as exc:
                p.error(str(exc))
            subs, transcript, transcript_error = None, None, None
            if not args.no_transcribe:
                try:
                    transcript = _run_transcribe(
                        got["path"], str(dest.with_suffix(".vtt")),
                        model=args.model, lang=args.lang, threads=args.threads)
                    subs = transcript["out"]
                except Exception as exc:  # Datei ist da; Transkript nachholbar
                    transcript_error = str(exc)
            updated = store.set_source_file(args.source, path=got["path"],
                                            subs_path=subs, title=args.title)
            out = {"source_id": args.source, "file": got, "subs": subs,
                   "status": updated["status"], "source": updated}
            if transcript:
                out["transcript"] = transcript
            if transcript_error:
                out["transcript_error"] = transcript_error
                out["hint"] = "Video liegt lokal — `transcribe --source <id>` nachholen"
            _dump(out)
        elif args.cmd == "transcribe":
            source = store.get_source(args.source)
            if source is None:
                p.error(f"source {args.source} not found")
            if not source.get("path"):
                p.error(f"source {args.source} has no local file — fetch it first")
            out = args.out or str(Path(source["path"]).with_suffix(".vtt"))
            got = _run_transcribe(source["path"], out, model=args.model,
                                  lang=args.lang, threads=args.threads)
            updated = store.set_source_file(args.source, path=source["path"],
                                            subs_path=got["out"])
            _dump({"source_id": args.source, "transcript": got,
                   "subs_path": updated.get("subs_path")})
        elif args.cmd == "crop-frame":
            try:
                box = _parse_box(args.box)
            except ValueError as exc:
                p.error(str(exc))
            _dump(crops.crop_frame(args.src, box, args.out,
                                   scale=args.scale, pad=args.pad))
        elif args.cmd == "candidates-add":
            try:
                items, warnings = _candidate_windows(_read_json(args.json))
            except ValueError as exc:
                p.error(str(exc))
            ids = store.add_candidates(args.source, items)
            _dump({"source": args.source, "added": ids, "warnings": warnings})
        elif args.cmd == "motion":
            if (args.source is None) == (args.clip is None):
                p.error("motion needs exactly one of --source or --clip")
            clip = store.get_clip(args.clip) if args.clip is not None else None
            source_id = clip["source_id"] if clip else args.source
            source = store.get_source(source_id)
            if not source or not source.get("path"):
                p.error(f"source {source_id} has no local file — download it first")
            start = args.from_s if args.from_s is not None else (
                clip["start_s"] if clip else None)
            end = args.to_s if args.to_s is not None else (
                clip["end_s"] if clip else None)
            if start is None or end is None:
                p.error("motion needs --from/--to (or --clip with a window)")
            try:
                got = motion.profile(source["path"], start=start, end=end,
                                     fps=args.fps, width=args.width,
                                     threshold=args.threshold)
            except ValueError as exc:
                p.error(str(exc))
            _dump({"source": source_id, "clip": args.clip, **got})
        elif args.cmd == "ocr":
            if (args.source is None) == (args.clip is None):
                p.error("ocr needs exactly one of --source or --clip")
            clip = store.get_clip(args.clip) if args.clip is not None else None
            source_id = clip["source_id"] if clip else args.source
            source = store.get_source(source_id)
            if not source or not source.get("path"):
                p.error(f"source {source_id} has no local file — download it first")
            try:
                box = _parse_box(args.box)
            except ValueError as exc:
                p.error(str(exc))
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
            got = ocr.scan(source["path"], box, times, engine=args.engine,
                           pad=args.pad, scale=args.scale, lo=args.min,
                           hi=args.max, debug_dir=args.debug_dir,
                           step=args.step if not args.at else 1.0)
            out = {"source": source_id, "clip": args.clip,
                   "box": list(box), "engine": got["engine"],
                   "checked": got["checked"], "first": got["first"],
                   "first_stable": got["first_stable"], "runs": got["runs"],
                   "empty": got["checked"] - len(got["hits"])}
            if args.all:
                out["hits"] = got["hits"]
            _dump(out)
        elif args.cmd == "boxes-set":
            try:
                got = store.set_boxes(args.source, _read_json(args.json))
            except (ValueError, KeyError) as exc:
                p.error(str(exc))
            _dump({"source": args.source, "boxes": got.get("boxes")})
        elif args.cmd == "boxes-get":
            _dump({"source": args.source, "boxes": store.get_boxes(args.source)})
        elif args.cmd == "recipe-set":
            try:
                got = store.set_recipe(args.source, args.recipe)
            except (ValueError, KeyError) as exc:
                p.error(str(exc))
            _dump({"source": args.source, "recipe": got.get("recipe")})
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
            _dump({"sources": store.list_sources(args.recipe)})
        elif args.cmd in ("exhaust", "reopen"):
            store.set_source_status(
                args.source, "Exhausted" if args.cmd == "exhaust" else "Downloaded")
            _dump(store.get_source(args.source))
        elif args.cmd in ("used", "skip"):
            clip = store.get_clip(args.clip)
            if clip is None:
                p.error(f"clip {args.clip} not found")
            status = "Used" if args.cmd == "used" else "Skipped"
            _dump(store.mark_clip(args.clip, status,
                                  video_id=getattr(args, "video_id", None)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
