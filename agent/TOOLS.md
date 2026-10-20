# TOOLS.md - Überblick

Einstieg: Wrapper, Pfade, Konventionen. **Details stehen in `modules/<name>/README.md`** -
hier nur, wohin man greift.

## Wrapper

Alle Module laufen über ein Skript (aus jedem cwd, von der exec-Policy erlaubt):

```
~/.openclaw/workspace-brainrothustler/bin/cli <modul>.cli [args.]
```

- aktiviert die venv und wechselt ins **Workspace-Root** - **kein** `cd`, kein
  `python3 -m .`.
- Relative Pfade beziehen sich damit auf den Workspace:
  `memory/videos/`, `memory/clips/`, `memory/screenshots/`, `memory/brainrot.db`.
- stdout = JSON, Fortschritt/Fehler = stderr.

## Konventionen

- Jedes CLI gibt **JSON** aus - parsen.
- Ergebnis = fertige `.mp4`: 9:16, Höhe = 1280.
- **Rezept** = inhaltliche Vorgabe (`recipes/<name>.md`). **Spec** = JSON für den
  Editor (ein Clip). Neue Rezepte aus `recipes/templates/yt_template.md`.

## Pfade

- Workspace-Root: `AGENTS.md`, `recipes/`, `skills/`, `memory/`
- **`memory/`** (Laufzeit, nicht im Git):
  - `videos/` - fertige Renders (`*.mp4`)
  - `clips/` - Rohmaterial / Downloads (`*.mp4`, `.json`, `.vtt`)
  - `screenshots/` - Frames, Crops, Standbilder (`*.png`)
  - `specs/` - Editor-Specs (`*.json`)
  - `brainrot.db` - Plan + Video-Gedächtnis
- **`modules/`** - nur Code.

## Module

- **editor** - Schnitt, Regionen/Layout, Bild-Overlays, Übergänge, Untertitel,
  Standbilder. Ein ffmpeg-Lauf pro Video. → `modules/editor/README.md`
- **yt_clips** - Quellen, Kandidaten, Status, OCR/Motion/Highlights. Rendert
  **nicht**. → `modules/yt_clips/README.md` (Prozess: `skills/ytclip`)
- **hosting** - Upload zu Cloudflare R2, öffentliche URL. → `modules/hosting/README.md`
- **longterm_memory** - Contentplan **und** Video-Gedächtnis (SQLite):
  `planned` → `generated` → `uploaded`. → `modules/longterm_memory/README.md`

## Ablauf in einem Satz

`longterm_memory.cli task` sagt, was ansteht (`plan` | `pipeline` | `upload` |
`idle`); `yt_clips next --recipe <name>` sagt, was am Rohmaterial fehlt
(`clip` | `find` | `download`); gerendert wird mit `editor` (validate → render),
danach `yt_clips used`.
