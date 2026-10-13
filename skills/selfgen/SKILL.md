---
name: selfgen
description: "Einen Prompt schreiben und mit `video_generate` ein selbstgemachtes Video erzeugen, dann rendern."
---

# Selbstgeneriertes Video

Ablauf, um mit dem generativen Modell ein Video von Grund auf zu bauen. Prozess
only — Thema, Stil, Struktur und Ton kommen aus dem Rezept `recipes/<name>.md`.

Das Frontmatter des Rezepts wählt das generative Modell: `model` ist ein
`provider/model`-Override (z. B. `kie/kling-2.6/text-to-video`); leer → der
OpenClaw-Standard (`agents.defaults.videoGenerationModel`). `audio: true|false`
setzt, ob das Modell Ton erzeugen soll. `action "list"` zeigt, was konfiguriert ist.

## Ablauf

1. **Rezept laden** (`read` `recipes/<name>.md`) — es legt Thema, Look, Struktur,
   Ton und Musik fest.
2. **Prompt schreiben** aus dem Rezept, mit dem Wissen über das Modell: eine klare
   Szene/Aktion, Einstellungsart, Kamerabewegung, Licht, Stil, Stimmung. Kurz und
   präzise schlägt lang und vage.
3. **Generieren** mit `video_generate` (action `generate`):
   - `prompt`: der Text aus Schritt 2
   - `model`: das `model` des Rezepts (weglassen/leer → Standard)
   - `aspectRatio`: `9:16`
   - `durationSeconds`: `8` (vom Anbieter begrenzt)
   - `resolution`: `720P` (oder `1080P`)
   - `audio`: das `audio` des Rezepts (`true` = Modell erzeugt Ton)
   Asynchron: der Aufruf liefert nur eine **Task-ID**. OpenClaw weckt diese Session,
   wenn das Video fertig ist — **nicht** in einer Schleife pollen; weiter, sobald es
   eintrifft. `action "status"` prüft den laufenden Task; `action "list"` zeigt Anbieter.
4. **Background-Track** aus dem Musik-Pool nehmen (`assets/music/` — siehe
   Asset-Liste des Rezepts) und auf die Videolänge trimmen. Überspringen, wenn das
   Modell eigenen Ton ausgibt (`audio: true`) und das Rezept keinen Track verlangt.
   Musik standardmäßig **nicht** generieren; `music_generate` nur nutzen, wenn ein
   Rezept es ausdrücklich verlangt.
5. **Konformen + editieren** mit `video_generation` (ein JSON → ein Video):
   `contain` / `on_background` auf `1080x1920`, plus `overlays`, `noise` und der
   gewählte Track in `audio` nach Rezept.
   ```
   python3 -m video_generation.cli probe --in raw.mp4
   python3 -m video_generation.cli render --recipe recipe.json
   ```
6. **Prüfen** und die `.mp4` an die Pipeline übergeben.

## Hinweise

- Erzeugt das Modell **keinen** Ton (`audio: false`, z. B. Google/Veo) → kommt der
  Ton aus dem Pool-Track (plus ggf. sfx), im `video_generation`-Schritt gemischt;
  `music_generate` ist ein optionales Extra, nicht der Standard. Gibt das Modell Ton
  aus (`audio: true`), diesen behalten und nur laut Rezept mischen.
- Die Dauer wird vom Anbieter begrenzt; für mehr als einen Clip mehrere generieren
  und `concat`en.
