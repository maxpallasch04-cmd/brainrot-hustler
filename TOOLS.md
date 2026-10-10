# TOOLS.md — lokale Konventionen (BrainrotHustler)

## Konventionen (gelten für alle Module)
- Jeden `python3 -m …`-Befehl aus `modules/` ausführen (oder `modules/` auf `PYTHONPATH`).
- Jedes CLI gibt **JSON** aus — parsen.
- Ergebnis eines Generierungsskills = fertig gerenderte `.mp4`.
- Vor dem Ausliefern prüfen: `probe` → 9:16, Höhe ≥ 1280 (sonst Rezept fixen, neu rendern).
- Rezepte: `recipes/<name>.md`; neue aus dem Art-Template in `recipes/templates/`.
- Details je Modul im jeweiligen `README.md`.

## Pfade
- Contentplan: `contentplan.md`
- Rezepte: `recipes/<name>.md` (Vorlagen `recipes/templates/<art>_template.md`)
- Skills: `skills/<name>/SKILL.md`
- DB (Langzeitgedächtnis): `data/brainrot.db` (override `BRAINROT_DB`)
- Downloads: `clips/<clip-id>.mp4`

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
python3 -m video_generation.cli render --recipe recipe.json      # oder --recipe -
python3 -m video_generation.cli cut --in raw.mp4 --start 12 --end 18 --out cut.mp4
```
(weitere: `background`, `overlay`, `noise`, `audio`, `concat`)

**hosting** — Upload → öffentliche URL; Download
```
python3 -m hosting.cli upload --file out.mp4                     # catbox (permanent, ≤200 MB)
python3 -m hosting.cli upload --file out.mp4 --expires 24h       # litterbox
python3 -m hosting.cli download --url <link> --out clips/x.mp4   # Direktlink → Datei
```

**longterm_memory** — Videos + Metriken
```
python3 -m longterm_memory.cli add-video --title "t" --art "Selbstgeneriert" --len-s 30 \
    --theme "story" --recipe "lifestory"
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
- `BRAINROT_DB` — DB-Pfad
