"""exec-friendly CLI over the Twitch clip discovery + download. JSON output.

Credentials come from the environment (TWITCH_CLIENT_ID / TWITCH_CLIENT_SECRET).
`download` needs no credentials.

Run from the project root:
    python3 -m twitch_clips.cli game-id --name "Fortnite"
    python3 -m twitch_clips.cli clips --game "Fortnite" --hours 168 --min-views 2000 \
        --top 10 --sort velocity --state data/twitch_seen.json
    python3 -m twitch_clips.cli download --id <clip-id> --out-dir clips
    ... clips --game ... | python3 -m twitch_clips.cli download --from-json -
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import discovery, download
from .helix import Helix


def _dump(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _load_seen(path: str | None) -> set[str]:
    if not path or not Path(path).exists():
        return set()
    return set(json.loads(Path(path).read_text(encoding="utf-8")))


def _save_seen(path: str | None, ids) -> None:
    if not path:
        return
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(sorted(set(ids)), indent=2), encoding="utf-8")


def _load_clips(src: str) -> list:
    """Accept a {'clips': [...]} object or a bare list, from a file or '-'."""
    data = (json.load(sys.stdin) if src == "-"
            else json.loads(Path(src).read_text(encoding="utf-8")))
    if isinstance(data, dict):
        data = data.get("clips", [])
    return list(data)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="twitch_clips")
    p.add_argument("--client-id", default=None, help="override TWITCH_CLIENT_ID")
    p.add_argument("--client-secret", default=None, help="override TWITCH_CLIENT_SECRET")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("game-id", help="resolve a category name to a game_id")
    g.add_argument("--name", required=True)

    c = sub.add_parser("clips", help="ranked viral clip shortlist for a category")
    c.add_argument("--game", default=None, help="category name, e.g. 'Fortnite'")
    c.add_argument("--game-id", default=None)
    c.add_argument("--hours", type=float, default=24)
    c.add_argument("--min-views", type=int, default=0)
    c.add_argument("--max-duration", type=float, default=None)
    c.add_argument("--language", default=None, help="e.g. 'en'")
    c.add_argument("--top", type=int, default=10)
    c.add_argument("--sort", choices=["views", "velocity"], default="views")
    c.add_argument("--max-pages", type=int, default=5)
    c.add_argument("--state", default=None, help="JSON file of already-seen clip ids")

    d = sub.add_parser("download", help="download clips via yt-dlp (no credentials)")
    d.add_argument("--url", default=None, help="clip URL")
    d.add_argument("--id", dest="clip_id", default=None, help="clip id / slug")
    d.add_argument("--from-json", default=None,
                   help="file (or '-') with {'clips': [...]} or a list of clips")
    d.add_argument("--out-dir", default=download.DEFAULT_OUT_DIR)
    d.add_argument("--top", type=int, default=None, help="only the first N clips")
    d.add_argument("--overwrite", action="store_true")

    args = p.parse_args(argv)

    if args.cmd == "download":
        if args.from_json:
            clips = _load_clips(args.from_json)
        elif args.url or args.clip_id:
            clips = [args.url or args.clip_id]
        else:
            p.error("download needs --url, --id or --from-json")
        result = download.download_clips(clips, args.out_dir, overwrite=args.overwrite,
                                         top=args.top)
        _dump({"out_dir": args.out_dir, "count": len(result["downloaded"]),
               **result})
        return 0

    client = Helix(args.client_id, args.client_secret)
    if args.cmd == "game-id":
        _dump({"name": args.name, "game_id": client.get_game_id(args.name)})
    elif args.cmd == "clips":
        seen = _load_seen(args.state)
        clips = discovery.find_clips(
            client, game=args.game, game_id=args.game_id, hours=args.hours,
            min_views=args.min_views, max_duration=args.max_duration,
            language=args.language, top=args.top, sort=args.sort,
            max_pages=args.max_pages, exclude_ids=seen,
        )
        _save_seen(args.state, seen | {c["id"] for c in clips})
        _dump({"game": args.game or args.game_id, "hours": args.hours,
               "sort": args.sort, "count": len(clips), "clips": clips})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
