"""exec-friendly CLI over the long-term memory. JSON output.

Run via the wrapper (works from any cwd):
    ~/.openclaw/workspace-brainrothustler/bin/cli longterm_memory.cli --channel sls <command>

The channel can also come from ``BRAINROT_CHANNEL`` (the wrapper does that).
Times (`--plan-at`, `--at`) accept either unix seconds or a local timestamp
like ``2026-10-21 18:00``.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime

from . import db
from .memory import LongTermMemory, Status, VideoArt


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


def _list(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _channel(args, required: bool = True) -> str | None:
    import brainrot_paths as paths

    if args.channel:
        value = paths.valid_channel(args.channel)
    else:
        value = paths.channel(required=required)
    return value


def _profile_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--niche", default=None, help="Nische in einem Satz")
    p.add_argument("--art", default=None, choices=[e.value for e in VideoArt])
    p.add_argument("--recipes", type=_list, default=None,
                   help="aktive Rezepte, kommasepariert")
    p.add_argument("--open-target", type=int, default=None,
                   help="wie viele offene Einträge es sein sollen")
    p.add_argument("--lead-h", type=float, default=None,
                   help="Vorlauf in Stunden")
    p.add_argument("--quiet-start", default=None, help="Ruhezeit ab, z. B. 22:00")
    p.add_argument("--quiet-end", default=None, help="Ruhezeit bis, z. B. 10:00")
    p.add_argument("--tz", default=None, help="Zeitzone, z. B. Europe/Berlin")
    p.add_argument("--format", default=None, help="Format, z. B. 9:16,1280")
    p.add_argument("--r2-prefix", default=None,
                   help="Key-Prefix im (geteilten) Bucket, z. B. brainrot/sls/")
    p.add_argument("--recipients", type=_list, default=None,
                   help="Empfänger-IDs, kommasepariert")
    p.add_argument("--active", type=int, default=None, choices=[0, 1])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="longterm_memory")
    p.add_argument("--db", default=None, help="DB path (default: memory/brainrot.db)")
    p.add_argument("--channel", default=None,
                   help="Kanal-ID (default: $BRAINROT_CHANNEL)")
    sub = p.add_subparsers(dest="cmd", required=True)

    cs = sub.add_parser("channel-set", help="Kanalprofil anlegen/ändern")
    _profile_args(cs)

    cg = sub.add_parser("channel-get", help="Kanalprofil lesen")
    sub.add_parser("channel-list", help="alle Kanäle")

    ap = sub.add_parser("add-plan", help="neuen Plan-Eintrag anlegen (status planned)")
    ap.add_argument("--idea", required=True, help="in einem Satz: was ist das Video")
    ap.add_argument("--recipe", required=True, help="Rezept-ID (recipes/<name>.md)")
    ap.add_argument("--plan-at", type=_ts, required=True,
                    help="geplante Uploadzeit (unix oder 'YYYY-MM-DD HH:MM')")
    ap.add_argument("--art", default=None, choices=[e.value for e in VideoArt],
                    help="Default: art des Kanalprofils")
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
    n.add_argument("--lead-h", type=float, default=None,
                   help="Vorlauf in Stunden (Default: Kanalprofil)")
    n.add_argument("--now", type=_ts, default=None,
                   help="Bezugszeit (Default: jetzt, für Tests)")

    t = sub.add_parser("task", help="Heartbeat-Entscheidung: upload | pipeline | plan | idle")
    t.add_argument("--open-target", type=int, default=None,
                   help="offene Einträge (Default: Kanalprofil)")
    t.add_argument("--lead-h", type=float, default=None,
                   help="Vorlauf in Stunden (Default: Kanalprofil)")
    t.add_argument("--now", type=_ts, default=None,
                   help="Bezugszeit (Default: jetzt, für Tests)")

    sub.add_parser("open-count", help="offene Einträge (planned + generated)")

    o = sub.add_parser("overdue", help="generiert, Uploadzeit vorbei")
    o.add_argument("--now", type=_ts, default=None)

    u = sub.add_parser("upload")
    u.add_argument("id", type=int)
    u.add_argument("--at", type=_ts, default=None)

    args = p.parse_args(argv)

    if args.cmd in ("channel-set", "channel-get", "channel-list"):
        with db.init_db(args.db) as _conn:  # noqa: F841  (schema anlegen)
            pass
        conn = db.init_db(args.db)
        try:
            if args.cmd == "channel-list":
                _dump(db.list_channels(conn))
                return 0
            cid = _channel(args)
            if args.cmd == "channel-get":
                _dump(db.get_channel(conn, cid))
                return 0
            fields = {k: v for k, v in vars(args).items()
                      if k not in ("cmd", "db", "channel") and v is not None}
            _dump(db.upsert_channel(conn, cid, **fields))
        finally:
            conn.close()
        return 0

    channel = _channel(args)
    lead_h = args.lead_h if "lead_h" in args and args.lead_h is not None else None

    with LongTermMemory(args.db, channel=channel) as mem:
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
            _dump(mem.nextDue(args.now, None if lead_h is None else int(lead_h * 3600)))
        elif args.cmd == "task":
            _dump(mem.task(args.now,
                           None if lead_h is None else int(lead_h * 3600),
                           args.open_target))
        elif args.cmd == "open-count":
            _dump({"channel": mem.channel, "open": mem.openCount()})
        elif args.cmd == "overdue":
            _dump(mem.overdue(args.now))
        elif args.cmd == "upload":
            mem.upload(args.id, args.at)
            _dump(mem.getVideo(args.id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
