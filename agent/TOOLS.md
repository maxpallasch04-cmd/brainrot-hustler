# TOOLS.md — Überblick

Einstieg: Wrapper, Pfade, Konventionen. **Details stehen in `modules/<name>/README.md`** —
hier nur, wohin man greift.

## Wrapper

Alle Module laufen über ein Skript (aus jedem cwd, von der exec-Policy erlaubt):

```
~/.openclaw/workspace-brainrothustler/bin/cli <modul>.cli [args…]
```

- aktiviert die venv und wechselt selbst nach `modules/` — **kein** `cd`, kein
  `python3 -m …`.
- Relative Pfade beziehen sich auf `modules/` (`clips/`, `data/brainrot.db`).
- stdout = JSON, Fortschritt/Fehler = stderr.

## Konventionen

- Jedes CLI gibt **JSON** aus — parsen.
- Ergebnis = fertige `.mp4`: 9:16, Höhe ≥ 1280.
- **Rezept** = inhaltliche Vorgabe (`recipes/<name>.md`). **Spec** = JSON für den
  Editor (ein Clip). Neue Rezepte aus `recipes/templates/yt_template.md`.

## Pfade

- Repo-Root: `contentplan.md`, `recipes/`, `skills/`
- Laufzeit unter `modules/`: `data/`, `clips/`, `frames/`
- DB: `modules/data/brainrot.db`

## Module

- **editor** — Schnitt, Regionen/Layout, Bild-Overlays, Übergänge, Untertitel,
  Standbilder. Ein ffmpeg-Lauf pro Video. → `modules/editor/README.md`
- **yt_clips** — Quellen, Kandidaten, Status, OCR/Motion/Highlights. Rendert
  **nicht**. → `modules/yt_clips/README.md` (Prozess: `skills/ytclip`)
- **hosting** — Upload zu Cloudflare R2, öffentliche URL. → `modules/hosting/README.md`
- **longterm_memory** — Videos + Metriken (Langzeitgedächtnis).
  → `modules/longterm_memory/README.md`
- **monitoring** — TikTok-Metriken/Report; vorerst **nicht angeschlossen**.
  → `modules/monitoring/README.md`

## Ablauf in einem Satz

`yt_clips next --recipe <name>` sagt, was ansteht (`clip` | `find` | `download`);
gerendert wird mit `editor` (validate → render), danach `yt_clips used`.
