"""exec-friendly CLI over the long-term memory. JSON output.

Run from the project root:
    python3 -m longterm_memory.cli <command> [args]
"""

from __future__ import annotations

import argparse
import json

from .memory import LongTermMemory, Status, VideoArt


def _dump(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="longterm_memory")
    p.add_argument("--db", default=None, help="DB path (default: data/brainrot.db)")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add-video")
    a.add_argument("--title", required=True)
    a.add_argument("--art", required=True, choices=[e.value for e in VideoArt])
    a.add_argument("--len-s", type=int, required=True)
    a.add_argument("--description", default="")
    a.add_argument("--theme", default="")
    a.add_argument("--recipe", default="", help="recipe name used to make the video")

    for name in ("get-video",):
        s = sub.add_parser(name)
        s.add_argument("id", type=int)

    l = sub.add_parser("list-videos")
    l.add_argument("--status", choices=[e.value for e in Status])

    u = sub.add_parser("upload")
    u.add_argument("id", type=int)
    u.add_argument("--at", type=int, default=None)

    m = sub.add_parser("add-metric")
    m.add_argument("id", type=int)
    m.add_argument("views", type=int)
    m.add_argument("comments", type=int)
    m.add_argument("likes", type=int)
    m.add_argument("--ts", type=int, default=None)

    n = sub.add_parser("newest-metric")
    n.add_argument("id", type=int)

    args = p.parse_args(argv)

    with LongTermMemory(args.db) as mem:
        if args.cmd == "add-video":
            _dump({"id": mem.addVideo(args.title, args.art, args.len_s,
                                      args.description, args.theme, args.recipe)})
        elif args.cmd == "get-video":
            _dump(mem.getVideo(args.id))
        elif args.cmd == "list-videos":
            _dump(mem.listVideos(args.status))
        elif args.cmd == "upload":
            mem.upload(args.id, args.at)
            _dump(mem.getVideo(args.id))
        elif args.cmd == "add-metric":
            mem.addMetric(args.id, args.views, args.comments, args.likes, args.ts)
            _dump({"ok": True})
        elif args.cmd == "newest-metric":
            _dump(mem.newestMetric(args.id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
