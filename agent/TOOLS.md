# TOOLS.md — Überblick (BrainrotHustler)

Einstieg: Wrapper, Konventionen, Pfade und die **wichtigsten Schritte** je Modul.
**Details (alle Flags, Formate, JSON-Felder) stehen im `modules/<name>/README.md`** —
hier nur so viel, dass du weißt, wohin du greifst.

## Aufruf: der Wrapper

Alle Module laufen über **ein** Skript (aus jedem cwd, von der exec-Policy erlaubt):

```
~/.openclaw/workspace-brainrothustler/bin/cli <modul.cli> [args…]
```

```
~/.openclaw/workspace-brainrothustler/bin/cli hosting.cli usage
```

- Der Wrapper aktiviert die venv und wechselt selbst nach `modules/` — **kein**
  `cd`, kein `source`, kein direktes `python3 -m …` (das ist nicht erlaubt).
- Relative Pfade in Befehlen beziehen sich damit auf `modules/`
  (z. B. `clips/`, `data/brainrot.db`).
- Module: `twitch_clips`, `video_generation`, `yt_clips`, `subtitles`, `hosting`,
  `longterm_memory`, `monitoring`.

## Konventionen (alle Module)

- Jedes CLI gibt **JSON** aus — parsen.
- Ergebnis eines Generierungsskills = fertig gerenderte `.mp4`.
- Vor dem Ausliefern prüfen: `probe` → 9:16, Höhe ≥ 1280 (sonst Rezept fixen, neu rendern).
- Rezepte: `recipes/<name>.md`; neue aus dem Art-Template in `recipes/templates/`.

## Pfade

**Zwei Wurzeln:** Repo-Dateien (`contentplan.md`, `recipes/`, `skills/`) liegen im
**Repo-Root**. Alles, was Module zur Laufzeit erzeugen (`data/`, `clips/`,
`frames/`), liegt relativ zu `modules/` → `modules/data/…`.
- Contentplan: `contentplan.md` (Repo-Root)
- Rezepte: `recipes/<name>.md` (Vorlagen `recipes/templates/<art>_template.md`)
- Skills: `skills/<name>/SKILL.md`
- DB (Langzeitgedächtnis): `modules/data/brainrot.db` (override `BRAINROT_DB`)
- Downloads: `modules/clips/<clip-id>.mp4`
- Frames (Vision): `modules/frames/` (aus `video_generation.cli frames`)
- Untertitel: `.vtt` (Transcript aus dem Download) / `.srt` (Clip-Fenster)

## Module — wichtigste Schritte

**twitch_clips** — virale Twitch-Clips finden + laden
```
~/.openclaw/workspace-brainrothustler/bin/cli twitch_clips.cli clips --game "<Game>" --hours 168 --min-views 5000 --top 10 --sort velocity --state data/twitch_seen.json
~/.openclaw/workspace-brainrothustler/bin/cli twitch_clips.cli download --id <clip-id> --out-dir clips
```
→ `modules/twitch_clips/README.md`

**video_generation** — schneiden / rendern / prüfen
```
~/.openclaw/workspace-brainrothustler/bin/cli video_generation.cli probe  --in raw.mp4
~/.openclaw/workspace-brainrothustler/bin/cli video_generation.cli frames --in raw.mp4 --count 4 --out-dir frames
~/.openclaw/workspace-brainrothustler/bin/cli video_generation.cli render --recipe recipe.json
```
→ `modules/video_generation/README.md`

**yt_clips** — YT-Clip-Art: Zustand, Format, Kandidaten, Clip rendern
```
~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli next                    # format | clip | find | download
~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli clip --clip <id> --out out.mp4 --size 1080x1920 --used
```
→ `modules/yt_clips/README.md` (Prozess + Vision: Skill `skills/ytclip`)

**subtitles** — Untertitel als eigenes Artefakt: Fenster schneiden + einbrennen
```
~/.openclaw/workspace-brainrothustler/bin/cli subtitles.cli cut  --in transcript.vtt --start 1200 --end 1220 --out clip.srt
~/.openclaw/workspace-brainrothustler/bin/cli subtitles.cli burn --in clip.mp4 --subs clip.srt --out out.mp4
```
→ `modules/subtitles/README.md`

**hosting** — Upload zu Cloudflare R2 → öffentliche URL; Download
```
~/.openclaw/workspace-brainrothustler/bin/cli hosting.cli upload --file out.mp4   # hochladen + aufräumen
~/.openclaw/workspace-brainrothustler/bin/cli hosting.cli usage                   # Objekte + freier Platz
```
→ `modules/hosting/README.md`

**longterm_memory** — Videos + Metriken
```
~/.openclaw/workspace-brainrothustler/bin/cli longterm_memory.cli add-video --title "<t>" --art "<art>" --len-s 30 --recipe "<name>"
~/.openclaw/workspace-brainrothustler/bin/cli longterm_memory.cli upload <id>
```
→ `modules/longterm_memory/README.md`

**monitoring** — TikTok-Metriken + Tagesreport
```
~/.openclaw/workspace-brainrothustler/bin/cli monitoring.cli token-status
~/.openclaw/workspace-brainrothustler/bin/cli monitoring.cli analyze --max 50
```
→ `modules/monitoring/README.md`

## Generativ (Text→Video)

OpenClaw-Tool `video_generate` (Google/Veo, `agents.defaults.videoGenerationModel`).
Parameter: `prompt`, `aspectRatio 9:16`, `durationSeconds 4|6|8`,
`resolution 720P|1080P`. Asynchron (Task-ID, Wake bei Fertig). Der Google/Veo-Pfad
generiert **kein Audio**.

## Musik

Standard: **vorgegebener Track aus dem Pool** `assets/music/` (siehe Rezept-Asset-Liste),
im Render via `video_generation` (`audio[]`) untermischen. Pro Video rotieren.

Optional/Extra: OpenClaw-Tool `music_generate` (Google/Lyria, gleicher Key) —
Parameter `prompt`, `instrumental: true`, `durationSeconds`. Asynchron (Task-ID,
Wake bei Fertig). **Nicht der Standard.**

## Env & Zugänge (nie ins Repo/Workspace)

- `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET` — twitch_clips
- **YouTube-Cookies** (`yt_clips`) — YouTube blockt Rechenzentrums-IPs
  („Sign in to confirm you're not a bot"). Cookies heilen den Bot-Check, **nicht**
  eine Sperre der IP selbst.
  - `YTDLP_COOKIES_FILE` — Pfad zur Netscape-`cookies.txt` (hat Vorrang)
  - `YTDLP_COOKIES_FROM_BROWSER` — z. B. `firefox:default` (nur Desktop)
  - sonst automatisch `$BRAINROT_STATE_DIR/cookies.txt`
    (Default `~/.openclaw/state/brainrot/cookies.txt`), wenn vorhanden
  - `YTDLP_PROXY` — nicht gesperrter Ausgang (z. B. `socks5://host:1080`);
    **die** Lösung, wenn die IP selbst geblockt ist
  - `YTDLP_EXTRACTOR_ARGS` — z. B. `youtube:player_client=tv,web_safari`
  - Die Datei ist ein Zugang → **außerhalb** Repo/Workspace. yt-dlp schreibt sie
    beim Lauf zurück (beschreibbar halten). Details: `modules/yt_clips/README.md`.
- `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `TIKTOK_REDIRECT_URI`,
  `TIKTOK_ACCESS_TOKEN`, `TIKTOK_TOKEN_FILE` — monitoring
  - Statische App-Creds kommen aus dem OpenClaw-Env (bzw. Team-Store).
  - Der **TikTok-Token** (access/refresh, **rotierend**) ist State, kein Config-Wert:
    liegt als Datei unter `~/.openclaw/state/brainrot/tiktok_token.json` —
    **nicht** im Repo/Workspace. `refresh` schreibt dort weiter.
- `BRAINROT_DB` — DB-Pfad
- **Hosting (Cloudflare R2)** — liegt im **OpenClaw-Team-Store** (Kind `env`), nicht
  mehr in einer `.env`. Das Gateway injiziert die Werte automatisch als
  Umgebungsvariablen in den exec-Kontext → `hosting` liest `os.environ`. Kein `.env`,
  kein Fallback. Setzen/Erneuern (pro Host, einmalig):
  `openclaw secrets store set R2_ACCOUNT_ID --kind env` (usw.) → `openclaw secrets reload`.
  Werte:
  - `R2_ACCOUNT_ID` — Cloudflare Account-ID
  - `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` — R2-API-Token (Object Read & Write)
  - `R2_BUCKET` — Bucket-Name
  - `R2_PUBLIC_BASE_URL` — `https://pub-xxxx.r2.dev` oder eigene Domain
  - optional: `R2_ENDPOINT`, `R2_PREFIX` (Default `videos/`), `R2_KEEP` (Default 1,
    behält nur das neueste Video), `R2_QUOTA_GB` (Default 10, Speicher-Obergrenze)
  - braucht `boto3`.
