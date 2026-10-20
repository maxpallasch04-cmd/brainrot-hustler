"""CLI: `validate`, `render`, `probe` — Ausgabe ist JSON auf stdout."""

from __future__ import annotations

import argparse
import json
import sys

from . import subs_cli
from .frames import frames as do_frames
from .probe import ProbeError, probe
from .spec import SpecError, load
from .render import render as do_render
from .validate import validate as do_validate


def _dump(obj, pretty: bool = False) -> None:
    if pretty:
        print(json.dumps(obj, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(obj, ensure_ascii=False))


def _utf8_console() -> None:
    """Windows-Konsole ist oft cp1252; JSON darf trotzdem UTF-8 sein."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    _utf8_console()
    parser = argparse.ArgumentParser(
        prog="editor.cli",
        description="JSON-Spec -> ffmpeg (validate / render / probe).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="Rezept prüfen (Randbedingungen + expect)")
    v.add_argument("--spec", required=True, help="Pfad zur Rezept-JSON")
    v.add_argument("--no-fs", action="store_true",
                   help="keine Datei-/Probe-Prüfung (nur Struktur und Geometrie)")
    v.add_argument("--pretty", action="store_true", help="JSON einrücken")

    r = sub.add_parser("render", help="Rezept rendern")
    r.add_argument("--spec", required=True, help="Pfad zur Rezept-JSON")
    r.add_argument("--out", help="Zielpfad (überschreibt 'out' im Rezept)")
    r.add_argument("--overwrite", action="store_true", help="vorhandene Datei ersetzen")
    r.add_argument("--dry-run", action="store_true",
                   help="nur den ffmpeg-Befehl ausgeben, nichts rendern")
    r.add_argument("--no-progress", action="store_true", help="kein Fortschritt auf stderr")
    r.add_argument("--preset", default="veryfast", help="x264 preset (Default: veryfast)")
    r.add_argument("--crf", type=int, default=20, help="x264 crf (Default: 20)")
    r.add_argument("--transition", type=float, default=None,
                   help="Übergang in Sekunden (Default: aus dem Rezept)")
    r.add_argument("--pretty", action="store_true", help="JSON einrücken")

    p = sub.add_parser("probe", help="Datei auslesen (Maße, Dauer, Ton)")
    p.add_argument("--in", dest="src", required=True)
    p.add_argument("--pretty", action="store_true", help="JSON einrücken")

    fr = sub.add_parser("frames", help="PNG-Standbilder aus einem Video")
    fr.add_argument("--in", dest="src", required=True)
    fr.add_argument("--at", default=None,
                   help="Sekunden, kommasepariert (Default: --count gleichmäßig)")
    fr.add_argument("--count", type=int, default=4, help="Anzahl (Default 4)")
    fr.add_argument("--out-dir", default="memory/screenshots")
    fr.add_argument("--width", type=int, default=None, help="herunterskalieren")
    fr.add_argument("--prefix", default=None, help="Dateinamen-Prefix")
    fr.add_argument("--pretty", action="store_true", help="JSON einrücken")

    subs_cli.add_parser(sub)

    args = parser.parse_args(argv)

    try:
        if args.cmd == "subtitles":
            return subs_cli.run(args)

        if args.cmd == "validate":
            rec = load(args.spec)
            report = do_validate(rec, check_fs=not args.no_fs)
            _dump(report, args.pretty)
            return 0 if report["ok"] else 1

        if args.cmd == "render":
            rec = load(args.spec)
            report = do_validate(rec)
            if not report["ok"]:
                _dump(report, args.pretty)
                return 1
            result = do_render(
                rec,
                out=args.out,
                overwrite=args.overwrite,
                dry_run=args.dry_run,
                progress=not args.no_progress,
                preset=args.preset,
                crf=args.crf,
                transition=args.transition,
                report=report,
            )
            _dump(result, args.pretty)
            return 0

        if args.cmd == "probe":
            info = probe(args.src)
            info["size"] = list(info["size"])
            _dump(info, args.pretty)
            return 0

        if args.cmd == "frames":
            times = None
            if args.at:
                times = [float(x) for x in args.at.replace(" ", "").split(",") if x]
            got = do_frames(args.src, times, count=args.count,
                            out_dir=args.out_dir, prefix=args.prefix,
                            width=args.width)
            _dump({"input": args.src, "count": len(got), "frames": got},
                  args.pretty)
            return 0

    except (SpecError, ProbeError) as exc:
        _dump({"ok": False, "error": str(exc)}, getattr(args, "pretty", False))
        return 2

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
