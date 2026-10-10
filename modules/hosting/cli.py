"""exec-friendly CLI over the hosting layer. JSON output.

Give it a file, get a link.

    python3 -m hosting.cli upload --file out.mp4
    python3 -m hosting.cli upload --file out.mp4 --expires 24h    # litterbox
    echo "hi" | python3 -m hosting.cli upload --file - --filename hello.txt

Anonymous by default; pass --userhash for account uploads (deleteable).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import catbox
from .download import download


def _dump(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="hosting")
    sub = p.add_subparsers(dest="cmd", required=True)

    u = sub.add_parser("upload", help="upload a file, print its URL")
    u.add_argument("--file", required=True, help="path, or - for stdin")
    u.add_argument("--filename", default=None, help="filename when reading stdin")
    u.add_argument("--expires", default=None, choices=catbox.LITTERBOX_TIMES,
                   help="self-expiring link via litterbox (else permanent catbox)")
    u.add_argument("--userhash", default=None, help="optional catbox account hash")
    u.add_argument("--timeout", type=int, default=180)

    d = sub.add_parser("download", help="download a URL to a file, print its path")
    d.add_argument("--url", required=True, help="direct http(s) link")
    d.add_argument("--out", default=None, help="output file path (or use --dir)")
    d.add_argument("--dir", default=None, help="output dir when --out is not given")
    d.add_argument("--timeout", type=int, default=180)
    d.add_argument("--max-mb", type=int, default=None, help="size cap in MB")

    args = p.parse_args(argv)

    if args.cmd == "upload":
        if args.file == "-":
            if not args.filename:
                p.error("--filename is required when reading from stdin")
            content = sys.stdin.buffer.read()
            url = catbox.upload_bytes(content, args.filename, expires=args.expires,
                                      userhash=args.userhash, timeout=args.timeout)
            size = len(content)
        else:
            size = Path(args.file).stat().st_size if Path(args.file).is_file() else None
            url = catbox.upload_file(args.file, expires=args.expires,
                                     userhash=args.userhash, timeout=args.timeout)
            args.filename = args.filename or Path(args.file).name
        _dump({
            "url": url,
            "host": "litterbox" if args.expires else "catbox",
            "expires": args.expires,
            "filename": args.filename,
            "bytes": size,
        })
        return 0
    if args.cmd == "download":
        kwargs = {}
        if args.max_mb:
            kwargs["max_bytes"] = args.max_mb * 1024 * 1024
        _dump(download(args.url, dest=args.out, out_dir=args.dir,
                       timeout=args.timeout, **kwargs))
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
