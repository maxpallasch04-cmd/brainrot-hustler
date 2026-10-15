"""exec-friendly CLI over the monitoring layer. JSON output.

Credentials: a TikTok user access token (`video.list` scope). Either
`TIKTOK_ACCESS_TOKEN` (static) or the OAuth flow:

    TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET  (Developer App)
    python3 -m monitoring.cli login            # -> data/tiktok_token.json

Run from the project root:
    python3 -m monitoring.cli login
    python3 -m monitoring.cli token-status
    python3 -m monitoring.cli user-stats
    python3 -m monitoring.cli list-videos --max 50
    python3 -m monitoring.cli analyze --max 50
    python3 -m monitoring.cli reports --limit 5
"""

from __future__ import annotations

import argparse
import json

from longterm_memory import LongTermMemory
from . import analysis
from .auth import TikTokAuth
from .metrics import TikTokMetrics
from .store import ReportStore


def _dump(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _build_metrics(args) -> TikTokMetrics:
    """Explicit token wins; else auto-refreshing token from the stored OAuth
    tokens (when app credentials are configured); else fall back to env."""
    if args.access_token:
        return TikTokMetrics(args.access_token)
    auth = TikTokAuth(token_path=args.token_file)
    if TikTokAuth.available() or auth.store.load():
        return TikTokMetrics(token_provider=lambda: auth.access_token())
    return TikTokMetrics()  # raises the usual missing-token error


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="monitoring")
    p.add_argument("--db", default=None, help="DB path (default: data/brainrot.db)")
    p.add_argument("--access-token", default=None, help="override TIKTOK_ACCESS_TOKEN")
    p.add_argument("--token-file", default=None, help="override TIKTOK_TOKEN_FILE")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("user-stats", help="account-level stats")

    v = sub.add_parser("list-videos", help="own public videos with metrics")
    v.add_argument("--max", type=int, default=50)

    a = sub.add_parser("analyze", help="fetch, match, build + store a report")
    a.add_argument("--max", type=int, default=50)
    a.add_argument("--no-blowup", action="store_true")

    r = sub.add_parser("reports", help="show stored reports")
    r.add_argument("--limit", type=int, default=5)

    lg = sub.add_parser("login", help="OAuth browser flow -> store user token")
    lg.add_argument("--port", type=int, default=None)
    lg.add_argument("--redirect-uri", default=None)
    lg.add_argument("--no-browser", action="store_true")
    lg.add_argument("--manual", action="store_true",
                    help="paste the redirect URL/code instead of a local server")
    lg.add_argument("--print-url", action="store_true",
                    help="headless: only print the authorize URL (step 1)")
    lg.add_argument("--finish", default=None, metavar="CODE_OR_URL",
                    help="headless: exchange a pasted redirect URL/code (step 2)")
    lg.add_argument("--timeout", type=int, default=300)

    sub.add_parser("token-status", help="show stored token state (no secrets)")
    sub.add_parser("refresh", help="force a token refresh")
    sub.add_parser("logout", help="revoke + delete the stored token")

    args = p.parse_args(argv)

    if args.cmd == "reports":
        with ReportStore(args.db) as store:
            _dump(store.recent(args.limit))
        return 0

    if args.cmd in ("login", "token-status", "refresh", "logout"):
        auth = TikTokAuth(token_path=args.token_file,
                          redirect_uri=getattr(args, "redirect_uri", None))
        if args.cmd == "login":
            if args.print_url:
                _dump({"url": auth.begin_login()})
            elif args.finish:
                auth.finish_login(args.finish)
                _dump(auth.status())
            else:
                auth.login(port=args.port, open_browser=not args.no_browser,
                           timeout=args.timeout, manual=args.manual)
                _dump(auth.status())  # masked: never print raw tokens
        elif args.cmd == "token-status":
            _dump(auth.status())
        elif args.cmd == "refresh":
            auth.refresh()
            _dump(auth.status())
        elif args.cmd == "logout":
            auth.revoke()
            _dump({"logged_in": False})
        return 0

    metrics = _build_metrics(args)
    if args.cmd == "user-stats":
        _dump(metrics.user_stats())
    elif args.cmd == "list-videos":
        _dump(metrics.list_recent(args.max))
    elif args.cmd == "analyze":
        videos = metrics.list_recent(args.max)
        with LongTermMemory(args.db) as mem, ReportStore(args.db) as store:
            _dump(analysis.run_analysis(mem, videos, store, blowup=not args.no_blowup))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
