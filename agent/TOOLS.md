# TOOLS.md - Überblick

Einstieg: Wrapper, Pfade, Konventionen. **Details stehen in `modules/<name>/README.md`** -
hier nur, wohin man greift.

## Wrapper

Alle Module laufen über ein Skript (aus jedem cwd, von der exec-Policy erlaubt):

```
~/.openclaw/workspace-brainrothustler/bin/cli --channel <id> <modul>.cli [args.]
```

- aktiviert die venv, setzt `modules/` auf den `PYTHONPATH` und wechselt ins
  **Workspace-Root**.
- `--channel <id>` kann an beliebiger Stelle stehen: der Wrapper exportiert es als
  `BRAINROT_CHANNEL` und entfernt es aus argv. Jedes Modul sieht nur das Env.
- **Ohne Kanal laufen nur `editor` und `hosting`** (und `channel-list`).
- Relative Pfade beziehen sich auf den Workspace.
- stdout = JSON, Fortschritt/Fehler = stderr.

## Konventionen

- Jedes CLI gibt **JSON** aus - parsen.
- Ergebnis = fertige `.mp4`: 9:16, Höhe = 1280 (Profilfeld `format`).
- **Rezept** = inhaltliche Vorgabe (`recipes/<name>.md`). **Spec** = JSON für den
  Editor (ein Clip). Neues Rezept: Datei anlegen, Aufbau wie die bestehenden.
- **Kanalprofil** = alles Kanalspezifische in der DB, nicht in Markdown.

## Pfade

- Workspace-Root: `AGENTS.md`, `recipes/`, `skills/`, `memory/`
- **`memory/`** (Laufzeit, nicht im Git):
  - `brainrot.db` - Kanäle, Plan, Video-Gedächtnis (eine DB, Spalte `channel_id`)
  - `<channel>/videos/` - fertige Renders
  - `<channel>/clips/` - Rohmaterial / Downloads (`.mp4`, `.json`, `.vtt`)
  - `<channel>/screenshots/` - Frames, Crops, Standbilder
  - `<channel>/specs/` - Editor-Specs
- **`modules/`** - nur Code.

## Module

- **editor** - Schnitt, Regionen/Layout, Bild-Overlays, Übergänge, Untertitel,
  Standbilder. Ein ffmpeg-Lauf pro Video. **Kanal-frei.** → `modules/editor/README.md`
- **yt_clips** - Quellen, Kandidaten, Status, OCR/Motion/Highlights. Rendert
  **nicht**. Kanalspezifisch (Quellen + Kandidaten). → `modules/yt_clips/README.md`
- **hosting** - Upload zu Cloudflare R2, öffentliche URL. Ein Bucket für alle
  Kanäle; getrennt nur durch `r2_prefix` aus dem Profil. → `modules/hosting/README.md`
- **longterm_memory** - Contentplan **und** Video-Gedächtnis (SQLite) plus
  Kanalprofile: `planned` → `generated` → `uploaded`.
  → `modules/longterm_memory/README.md`

## Kanalprofil

```
bin/cli --channel sls longterm_memory.cli channel-get
bin/cli --channel sls longterm_memory.cli channel-set --niche "Skate comps" \
    --recipes ytsls-besttrick,ytsls-bestline --open-target 2 --lead-h 4 \
    --quiet-start 22:00 --quiet-end 10:00 --tz Europe/Berlin
bin/cli longterm_memory.cli channel-list          # ohne --channel
```

## Ablauf in einem Satz

`longterm_memory.cli task` sagt, was ansteht (`upload` | `pipeline` | `plan` |
`idle`); `yt_clips next --recipe <name>` sagt, was am Rohmaterial fehlt
(`clip` | `find` | `download`); gerendert wird mit `editor` (validate → render),
danach `yt_clips used`.
