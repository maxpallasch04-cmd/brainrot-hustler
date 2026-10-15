# TOOLS.md — lokale Konventionen (BrainrotHustler)

## Konventionen (gelten für alle Module)
- Jeden `python3 -m …`-Befehl aus `modules/` ausführen.
- Jedes CLI gibt **JSON** aus — parsen.
- Ergebnis eines Generierungsskills = fertig gerenderte `.mp4`.
- Vor dem Ausliefern prüfen: `probe` → 9:16, Höhe ≥ 1280 (sonst Rezept fixen, neu rendern).
- Rezepte: `recipes/<name>.md`; neue aus dem Art-Template in `recipes/templates/`.
- Details je Modul im jeweiligen `README.md`.

## Pfade
**Zwei Wurzeln:** Repo-Dateien (`contentplan.md`, `recipes/`, `skills/`) liegen im
**Repo-Root**. Alles, was Module zur Laufzeit erzeugen (`data/`, `clips/`,
`frames/`), liegt relativ zum **Arbeitsverzeichnis `modules/`** → `modules/data/…`.
- Contentplan: `contentplan.md` (Repo-Root)
- Rezepte: `recipes/<name>.md` (Vorlagen `recipes/templates/<art>_template.md`)
- Skills: `skills/<name>/SKILL.md`
- DB (Langzeitgedächtnis): `modules/data/brainrot.db` (override `BRAINROT_DB`)
- Downloads: `modules/clips/<clip-id>.mp4`
- Frames (Vision): `modules/frames/` (aus `video_generation.cli frames`)
- Untertitel: `.vtt` (Transcript aus dem Download) / `.srt` (Clip-Fenster)

## Module (exakte Befehle, aus `modules/`)

**twitch_clips** — Clips finden/laden
```
python3 -m twitch_clips.cli game-id --name "Fortnite"
python3 -m twitch_clips.cli clips --game "Fortnite" --hours 168 --min-views 5000 \
    --top 10 --sort velocity --state data/twitch_seen.json
python3 -m twitch_clips.cli clips ... | python3 -m twitch_clips.cli download --from-json - --out-dir clips
```

**video_generation** — schneiden/rendern
```
python3 -m video_generation.cli probe --in raw.mp4
python3 -m video_generation.cli frames --in raw.mp4 --count 4 --out-dir frames
python3 -m video_generation.cli render --recipe recipe.json      # oder --recipe -
python3 -m video_generation.cli cut --in raw.mp4 --start 12 --end 18 --out cut.mp4
python3 -m video_generation.cli crop --in raw.mp4 --out r.mp4 --box 300,300,1400,800
python3 -m video_generation.cli layout --in match.mp4 --out clip.mp4 \
    --regions regions.json --size 1080x1920 --start 1200 --end 1235
```
(weitere: `background`, `overlay`, `crop`, `layout`, `noise`, `audio`, `concat`)

**yt_clips** — YT-Clip-Art: Quelle/Format/Clip-State (4 Screenshots → Vision → Format)
Vision-Modell = OpenClaw `agents.defaults.imageModel`.
```
python3 -m yt_clips.cli next                                      # format | clip | find | download
python3 -m yt_clips.cli download --url <url> --out-dir clips --recipe <name>
python3 -m yt_clips.cli format-set --source 3 --regions fmt.json
python3 -m yt_clips.cli candidates-add --source 3 --json cands.json
python3 -m yt_clips.cli highlights --source 3 --top 10 --add    # optional: Kapitel+Audio-Peaks
python3 -m yt_clips.cli clip --clip 5 --out out.mp4 --size 1080x1920 --used
python3 -m yt_clips.cli list
```
Prozess: Skill `skills/ytclip`; State in `data/brainrot.db` (`yt_source`, `yt_clip`).

**subtitles** — Untertitel als eigenes Artefakt: Fenster schneiden + einbrennen
```
python3 -m subtitles.cli cut  --in transcript.vtt --start 1200 --end 1220 --out clip.srt
python3 -m subtitles.cli numbers --in transcript.vtt --min 6 --max 10   # Score-Anker
python3 -m subtitles.cli burn --in clip.mp4 --subs clip.srt --out out.mp4 --font-size 64 --margin-v 220
```

**hosting** — Upload zu Cloudflare R2 → öffentliche URL; Download
```
python3 -m hosting.cli upload --file out.mp4                     # hochladen + aufräumen (R2)
python3 -m hosting.cli upload --file out.mp4 --no-prune          # ohne Aufräumen
python3 -m hosting.cli usage                                     # Objekte + freier Platz
python3 -m hosting.cli prune                                     # manuell aufräumen
python3 -m hosting.cli download --url <link> --out clips/x.mp4   # Direktlink → Datei
```

**longterm_memory** — Videos + Metriken
```
python3 -m longterm_memory.cli add-video --title "t" --art "Selbstgeneriert" --len-s 30 \
    --theme "horror" --recipe "gencreep"
python3 -m longterm_memory.cli get-video 1
python3 -m longterm_memory.cli list-videos [--status Created|Uploaded]
python3 -m longterm_memory.cli upload 1 [--at <unix_ts>]
python3 -m longterm_memory.cli add-metric 1 1200 30 90
python3 -m longterm_memory.cli newest-metric 1
```

**monitoring** — TikTok-Metriken + Report
```
python3 -m monitoring.cli token-status
python3 -m monitoring.cli user-stats
python3 -m monitoring.cli list-videos --max 50
python3 -m monitoring.cli analyze --max 50
python3 -m monitoring.cli reports --limit 5
```

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

## Env (Secrets, nie in Dateien)
- `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET` — twitch_clips
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
