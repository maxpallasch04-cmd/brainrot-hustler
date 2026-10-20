"""exec-friendly CLI over the long-term memory. JSON output.

Run via the wrapper (works from any cwd):
    ~/.openclaw/workspace-brainrothustler/bin/cli longterm_memory.cli <command> [args]

Times (`--plan-at`, `--at`) accept either unix seconds or a local timestamp
like ``2026-10-21 18:00``.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime

from .memory import DEFAULT_LEAD_S, LongTermMemory, Status, VideoArt


def _dump(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _ts(value: str) -> int:
    """Unix seconds or a local date/time (``YYYY-MM-DD[ HH:MM[:SS]]``)."""
    raw = value.strip()
    if raw.isdigit():
        return int(raw)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return int(datetime.strptime(raw, fmt).timestamp())
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(
        f"invalid time {value!r} (unix seconds or 'YYYY-MM-DD HH:MM')"
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="longterm_memory")
    p.add_argument("--db", default=None, help="DB path (default: memory/brainrot.db)")
    sub = p.add_subparsers(dest="cmd", required=True)

    ap = sub.add_parser("add-plan", help="neuen Plan-Eintrag anlegen (status planned)")
    ap.add_argument("--idea", required=True, help="in einem Satz: was ist das Video")
    ap.add_argument("--recipe", required=True, help="Rezept-ID (recipes/<name>.md)")
    ap.add_argument("--plan-at", type=_ts, required=True,
                    help="geplante Uploadzeit (unix oder 'YYYY-MM-DD HH:MM')")
    ap.add_argument("--art", default=VideoArt.YT_CLIP.value,
                    choices=[e.value for e in VideoArt])
    ap.add_argument("--theme", default="")

    g = sub.add_parser("generated", help="Render eintragen (status generated)")
    g.add_argument("id", type=int)
    g.add_argument("--title", required=True)
    g.add_argument("--description", default="")
    g.add_argument("--file", required=True, help="Pfad zur fertigen mp4")
    g.add_argument("--len-s", type=int, required=True)
    g.add_argument("--art", default=None, choices=[e.value for e in VideoArt])
    g.add_argument("--theme", default=None)

    for name in ("get-video",):
        s = sub.add_parser(name)
        s.add_argument("id", type=int)

    l = sub.add_parser("list-videos")
    l.add_argument("--status", choices=[e.value for e in Status])

    n = sub.add_parser("nextdue", help="nächster fälliger Plan-Eintrag (planned)")
    n.add_argument("--lead-h", type=float, default=DEFAULT_LEAD_S / 3600,
                   help="Vorlauf in Stunden (Default 4)")
    n.add_argument("--now", type=_ts, default=None,
                   help="Bezugszeit (Default: jetzt, für Tests)")

    t = sub.add_parser("task", help="Heartbeat-Entscheidung: upload | pipeline | plan | idle")
    t.add_argument("--open-target", type=int, default=2,
                   help="wie viele offene Einträge es sein sollen (Default 2)")
    t.add_argument("--lead-h", type=float, default=DEFAULT_LEAD_S / 3600,
                   help="Vorlauf in Stunden (Default 4)")
    t.add_argument("--now", type=_ts, default=None,
                   help="Bezugszeit (Default: jetzt, für Tests)")

    sub.add_parser("open-count", help="offene Einträge (planned + generated)")

    o = sub.add_parser("overdue", help="generiert, Uploadzeit vorbei")
    o.add_argument("--now", type=_ts, default=None)

    u = sub.add_parser("upload")
    u.add_argument("id", type=int)
    u.add_argument("--at", type=_ts, default=None)

    args = p.parse_args(argv)

    with LongTermMemory(args.db) as mem:
        if args.cmd == "add-plan":
            _dump({"id": mem.addPlan(args.idea, args.recipe, args.plan_at,
                                     art=args.art, theme=args.theme)})
        elif args.cmd == "generated":
            mem.markGenerated(args.id, title=args.title, description=args.description,
                              file=args.file, len_s=args.len_s,
                              art=args.art, theme=args.theme)
            _dump(mem.getVideo(args.id))
        elif args.cmd == "get-video":
            _dump(mem.getVideo(args.id))
        elif args.cmd == "list-videos":
            _dump(mem.listVideos(args.status))
        elif args.cmd == "nextdue":
            _dump(mem.nextDue(args.now, int(args.lead_h * 3600)))
        elif args.cmd == "task":
            _dump(mem.task(args.now, int(args.lead_h * 3600), args.open_target))
        elif args.cmd == "open-count":
            _dump({"open": mem.openCount()})
        elif args.cmd == "overdue":
            _dump(mem.overdue(args.now))
        elif args.cmd == "upload":
            mem.upload(args.id, args.at)
            _dump(mem.getVideo(args.id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
