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

import brainrot_paths as paths

#: Default download target: ``memory/<channel>/clips`` (see brainrot_paths).
DEFAULT_OUT_DIR = None

#: Zielhöhe in Pixeln. 1080 ist der Kompromiss: die 9:16-Action-Box wird danach
#: nur ~1,8x hochskaliert, OCR hat genug Pixel, und der Decode bleibt bezahlbar.
#: Abweichen nur in Ausnahmen (sehr kleine Score-Einblendungen -> 1440).
DEFAULT_QUALITY = 1080


def format_selector(quality: int | None = DEFAULT_QUALITY) -> str:
    """yt-dlp-Format: bestes Video+Audio bis `quality` Höhe, danach gemerged.

    ``None``/``0`` fällt auf das alte Verhalten zurück (beste *fertige* MP4) -
    das ist auf YouTube oft nur 360p oder 720p.
    """
    if not quality:
        return "mp4/best"
    q = int(quality)
    return f"bv*[height<={q}]+ba/b[height<={q}]/b"


def progressive_selector(quality: int | None = DEFAULT_QUALITY) -> str:
    """Beste **fertige** Datei (Video+Ton) bis `quality` - braucht keinen PO-Token."""
    q = int(quality or DEFAULT_QUALITY)
    return f"b[height<={q}]/b"


def _is_gated(exc: Exception) -> bool:
    """403 oder "kein Format": beides heißt, der Client liefert nichts Brauchbares."""
    text = str(exc).lower()
    return ("403" in text or "forbidden" in text
            or "requested format is not available" in text)


def _ffmpeg_location() -> str | None:
    """Verzeichnis des ffmpeg-Binaries für den Merge (imageio-ffmpeg reicht)."""
    try:
        from editor.probe import ffmpeg_exe

        return str(Path(ffmpeg_exe()).parent)
    except Exception:
        return None


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
             subs_lang: str | None = None, quality: int | None = DEFAULT_QUALITY) -> dict:
    """Download one video (+ optional subtitles); returns the file facts.

    ``subs_lang`` (e.g. ``"en"``) also fetches the transcript (auto-captions,
    VTT) and returns its path as ``subs``. ``quality`` ist die maximale Höhe in
    Pixeln (Default 1080); Video und Audio werden dafür getrennt geladen und
    mit ffmpeg zu einer MP4 gemerged.
    """
    out_dir = out_dir or paths.channel_dir("clips")
    try:
        import yt_dlp
    except ImportError as exc:  # pragma: no cover - depends on host
        raise RuntimeError("yt-dlp is not installed (python3 -m pip install yt-dlp)") from exc

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    opts = {
        "outtmpl": str(out / "%(id)s.%(ext)s"),
        "format": format_selector(quality),
        "merge_output_format": "mp4",
        "quiet": quiet,
        "no_warnings": quiet,
        "noprogress": True,
        "overwrites": bool(overwrite),
        "noplaylist": True,
    }
    ffmpeg = _ffmpeg_location()
    if ffmpeg:
        opts["ffmpeg_location"] = ffmpeg
    opts.update(cookie_opts())
    opts.update(net_opts())
    if subs_lang:
        opts.update({
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": [subs_lang],
            "subtitlesformat": "vtt",
        })

    def _fetch(options: dict):
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            requested = (info.get("requested_downloads") or [{}])[0]
            path = requested.get("filepath") or ydl.prepare_filename(info)
            subs_path = None
            for meta in (info.get("requested_subtitles") or {}).values():
                if meta.get("filepath"):
                    subs_path = str(meta["filepath"])
                    break
        return info, path, subs_path

    used_format = opts["format"]
    fallback = False
    try:
        info, path, subs_path = _fetch(opts)
    except Exception as exc:
        # 403 trotz PO-Token: DASH-Streams sind gated, progressive nicht.
        if not quality or not _is_gated(exc):
            raise _with_hint(exc) from exc
        retry = dict(opts)
        retry["format"] = progressive_selector(quality)
        retry["overwrites"] = True
        info, path, subs_path = _fetch(retry)
        used_format = retry["format"]
        fallback = True

    out = {"path": str(path), "id": info.get("id") or youtube_id(url),
           "title": info.get("title") or "", "duration_s": info.get("duration"),
           "chapters": info.get("chapters") or [], "subs": subs_path,
           "format": used_format}
    if fallback:
        out["quality_fallback"] = True
    return out
