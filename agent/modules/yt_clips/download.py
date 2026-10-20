"""Download a YouTube video with yt-dlp.

Accepts a URL (watch / youtu.be / shorts). The file lands in
``out_dir/<ext-id>.<ext>``; existing files are reused unless ``overwrite=True``.
Returns ``{path, id, title, duration_s}``.

YouTube gates datacenter IPs behind "Sign in to confirm you're not a bot", so a
logged-in session (cookies) is usually required — see ``cookie_opts()``.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

DEFAULT_OUT_DIR = "memory/clips"


def default_cookies_file() -> Path:
    """Default cookie location: ``$BRAINROT_STATE_DIR/cookies.txt``."""
    state_dir = Path(os.environ.get("BRAINROT_STATE_DIR")
                     or Path.home() / ".openclaw" / "state" / "brainrot")
    return state_dir / "cookies.txt"


def cookie_opts() -> dict:
    """yt-dlp auth options for YouTube's bot gate (empty when unconfigured).

    Cookies are credentials: keep them outside the repo/workspace (like the
    TikTok token). Resolution order:

    - ``YTDLP_COOKIES_FILE`` — path to a Netscape ``cookies.txt`` (yt-dlp
      refreshes it in place, so it should be writable).
    - ``YTDLP_COOKIES_FROM_BROWSER`` — e.g. ``chrome`` / ``firefox:default``;
      handy on a desktop, unavailable on a headless host.
    - else ``$BRAINROT_STATE_DIR/cookies.txt`` if that file exists.
    """
    path = os.environ.get("YTDLP_COOKIES_FILE", "").strip()
    if path:
        return {"cookiefile": str(Path(path).expanduser())}
    browser = os.environ.get("YTDLP_COOKIES_FROM_BROWSER", "").strip()
    if browser:
        return {"cookiesfrombrowser": tuple(p.strip() for p in browser.split(":") if p.strip())}
    default = default_cookies_file()
    if default.is_file():
        return {"cookiefile": str(default)}
    return {}


def _parse_extractor_args(raw: str) -> dict:
    """``youtube:player_client=tv,web_safari`` -> ``{'youtube': {'player_client': [...]}}``.

    Mirrors yt-dlp's own ``--extractor-args`` parsing: one ``IE:ARGS`` pair,
    args separated by ``;``, values by unescaped commas (``\\,`` escapes one).
    """
    ie, _, rest = raw.partition(":")
    if not rest:
        return {}
    fields = {}
    for arg in rest.split(";"):
        key, sep, vals = arg.partition("=")
        if not sep:
            continue
        fields[key.strip().lower().replace("-", "_")] = [
            v.replace("\\,", ",").strip() for v in re.split(r"(?<!\\),", vals)
        ]
    return {ie.strip(): fields} if fields else {}


def net_opts() -> dict:
    """Optional network escape hatches from the environment (empty when unset).

    YouTube blocks many datacenter IPs outright — cookies alone do not lift a
    block on the **IP**. These are the levers for that case:

    - ``YTDLP_PROXY`` — an exit that is not blocked, e.g.
      ``socks5://user:pass@host:1080`` or ``http://host:8080``. A residential/
      mobile IP works best, ideally in the same region as the cookie session.
    - ``YTDLP_EXTRACTOR_ARGS`` — e.g. ``youtube:player_client=tv,web_safari``
      (mirrors yt-dlp's ``--extractor-args``).
    - ``YTDLP_JS_RUNTIMES`` — e.g. ``node`` or ``node:/usr/bin/node,deno``.
      yt-dlp only enables **deno** by default, so an installed Node is ignored
      unless it is listed here (YouTube needs a JS runtime for the signature
      challenge).
    """
    opts: dict = {}
    proxy = os.environ.get("YTDLP_PROXY", "").strip()
    if proxy:
        opts["proxy"] = proxy
    raw = os.environ.get("YTDLP_EXTRACTOR_ARGS", "").strip()
    if raw:
        args = _parse_extractor_args(raw)
        if args:
            opts["extractor_args"] = args
    runtimes = os.environ.get("YTDLP_JS_RUNTIMES", "").strip()
    if runtimes:
        # yt-dlp's API wants {runtime: {'path': ...}} (the CLI converts from
        # 'RUNTIME[:PATH]' strings) — mirror that here.
        js: dict = {}
        for item in runtimes.split(","):
            item = item.strip()
            if not item:
                continue
            name, _, path = item.partition(":")
            js[name.strip().lower()] = {"path": path.strip() or None}
        if js:
            opts["js_runtimes"] = js
    elif shutil.which("node"):
        # yt-dlp only enables deno by default. Node is usually installed and is
        # needed for YouTube's n challenge; passing it explicitly avoids the
        # silent "Some formats may be missing" / "Requested format is not
        # available" failure.
        opts["js_runtimes"] = {"node": {"path": None}}
    return opts


def _with_hint(exc: Exception) -> Exception:
    """Turn YouTube's bot-check failure into an actionable message."""
    msg = str(exc)
    if any(s in msg for s in ("Sign in to confirm", "not a bot")):
        return RuntimeError(
            "YouTube bot check: a signed-in session is required. Provide cookies "
            f"(Netscape cookies.txt at {default_cookies_file()}, or set "
            "YTDLP_COOKIES_FILE / YTDLP_COOKIES_FROM_BROWSER)."
        )
    return exc

_YT_ID = re.compile(r"(?:v=|youtu\.be/|shorts/|embed/|/v/)([A-Za-z0-9_-]{6,})")


def youtube_id(url: str) -> str | None:
    """Best-effort YouTube video id from a URL."""
    m = _YT_ID.search(str(url))
    return m.group(1) if m else None


def download(url: str, out_dir=DEFAULT_OUT_DIR, *, overwrite=False, quiet=True,
             subs_lang: str | None = None) -> dict:
    """Download one video (+ optional subtitles); returns the file facts.

    ``subs_lang`` (e.g. ``"en"``) also fetches the transcript (auto-captions,
    VTT) and returns its path as ``subs``.
    """
    try:
        import yt_dlp
    except ImportError as exc:  # pragma: no cover - depends on host
        raise RuntimeError("yt-dlp is not installed (python3 -m pip install yt-dlp)") from exc

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    opts = {
        "outtmpl": str(out / "%(id)s.%(ext)s"),
        "format": "mp4/best",
        "quiet": quiet,
        "no_warnings": quiet,
        "noprogress": True,
        "overwrites": bool(overwrite),
        "noplaylist": True,
    }
    opts.update(cookie_opts())
    opts.update(net_opts())
    if subs_lang:
        opts.update({
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": [subs_lang],
            "subtitlesformat": "vtt",
        })

    subs_path = None
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
        except Exception as exc:
            raise _with_hint(exc) from exc
        requested = (info.get("requested_downloads") or [{}])[0]
        path = requested.get("filepath") or ydl.prepare_filename(info)
        for meta in (info.get("requested_subtitles") or {}).values():
            if meta.get("filepath"):
                subs_path = str(meta["filepath"])
                break
    return {"path": str(path), "id": info.get("id") or youtube_id(url),
            "title": info.get("title") or "", "duration_s": info.get("duration"),
            "chapters": info.get("chapters") or [], "subs": subs_path}
