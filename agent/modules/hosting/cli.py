"""exec-friendly CLI over the hosting layer. JSON output.

Give it a file, get a link — always your Cloudflare R2 bucket.

    python3 -m hosting.cli upload --file out.mp4
    echo "hi" | python3 -m hosting.cli upload --file - --filename hello.txt
    python3 -m hosting.cli usage
    python3 -m hosting.cli prune

Config comes from the environment (OpenClaw store/env, see ``TOOLS.md``). Uploads prune
old objects afterwards: only the newest ``R2_KEEP`` survive (default 1), and the
total stays under ``R2_QUOTA_GB``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import r2
from .download import download


def _dump(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="hosting")
    sub = p.add_subparsers(dest="cmd", required=True)

    u = sub.add_parser("upload", help="upload a file to R2, print its URL")
    u.add_argument("--file", required=True, help="path, or - for stdin")
    u.add_argument("--filename", default=None, help="filename when reading stdin")
    u.add_argument("--key", default=None, help="object key override")
    u.add_argument("--no-prune", action="store_true", help="keep old objects")
    u.add_argument("--timeout", type=int, default=180)

    pr = sub.add_parser("prune", help="delete old objects (keep newest R2_KEEP)")
    pr.add_argument("--keep", type=int, default=None, help="override R2_KEEP")
    pr.add_argument("--quota-gb", type=float, default=None, help="override R2_QUOTA_GB")

    sub.add_parser("usage", help="show stored objects and free space")

    d = sub.add_parser("download", help="download a URL to a file, print its path")
    d.add_argument("--url", required=True, help="direct http(s) link")
    d.add_argument("--out", default=None, help="output file path (or use --dir)")
    d.add_argument("--dir", default=None, help="output dir when --out is not given")
    d.add_argument("--timeout", type=int, default=180)
    d.add_argument("--max-mb", type=int, default=None, help="size cap in MB")

    args = p.parse_args(argv)

    if args.cmd == "upload":
        cfg = r2.config()
        if args.file == "-":
            if not args.filename:
                p.error("--filename is required when reading from stdin")
            content = sys.stdin.buffer.read()
            filename = args.filename
            size = len(content)
        else:
            content = None
            filename = args.filename or Path(args.file).name
            size = Path(args.file).stat().st_size if Path(args.file).is_file() else None
        key = args.key or r2.object_key(filename, prefix=cfg["prefix"])
        if content is not None:
            url = r2.upload_bytes(content, filename, key=key, timeout=args.timeout)
        else:
            url = r2.upload_file(args.file, key=key, timeout=args.timeout)
        out = {"url": url, "host": "r2", "bucket": cfg["bucket"], "key": key,
               "filename": filename, "bytes": size}
        if not args.no_prune:
            try:
                out["pruned"] = r2.prune(protect={key})
            except r2.R2Error as exc:  # upload succeeded — report, don't fail
                out["prune_error"] = str(exc)
        _dump(out)
        return 0
    if args.cmd == "prune":
        quota = int(args.quota_gb * 1024 ** 3) if args.quota_gb is not None else None
        _dump(r2.prune(keep=args.keep, quota=quota))
        return 0
    if args.cmd == "usage":
        _dump(r2.usage())
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
