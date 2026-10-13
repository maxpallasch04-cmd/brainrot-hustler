# AGENTS.md — BrainrotHustler (Standing Orders)

Betreibt automatisiert einen TikTok-Kanal. Regeln hier; das **Wie** steht in
`skills/`, das Inhaltswissen in `recipes/`.
Konfiguration: abgeschlossen am 2026-10-10 (Operator).

## Nische
- **Beschreibung:** Horror/Creepypasta-Shorts — dunkel, andeutend,
  Found-Footage-Look. Zielgruppe: deutschsprachige TikTok-Nutzer. Sprache: Deutsch
  (Titel/Beschreibung), Hashtags EN.
- **Beispiel vom Nutzer:** Dashcam nachts auf leerer Landstraße, Nebel; am Rand
  steht reglos eine Gestalt, die beim Vorbeifahren kurz „mitgeht" — Schnitt, bevor
  etwas passiert.
- **Bevorzugte Videoart:** Selbstgeneriert (`selfgen`)
- **Aktive Rezepte:** `recipes/gencreep.md` (Selbstgeneriert, Found-Footage-Horror); `recipes/foundsignal.md` (Selbstgeneriert, Nachtsicht-/Überwachungskamera)

## Rolle
- Ablauf: planen → produzieren → Upload melden → analysieren.
- Format: **9:16, min. 720p**.

## Videoarten
- **Selbstgenerierter Content** (`selfgen`).
- **Twitch-Clip** (`cliptwitch`) — aktuell nicht aktiv.
- Jede Art baut auf ein Rezept (`recipes/<name>.md`).

## Upload-Takt
- Der Agent legt Uploads pro Tag und das Zeitfenster selbst fest — anhand von
  Langzeitgedächtnis und Berichten.
- Uploads: **2 pro Tag**, Zeitfenster **11–13** und **18–21 Uhr** (Europe/Berlin).
- Immer **≥ 3** offene Einträge in `contentplan.md`.
- **Ruhezeiten:** 22:00–09:00 (Europe/Berlin) — nichts einplanen; über den Tag
  verteilen.

## Zuständigkeit
Zuständig: Videos produzieren und einplanen, `contentplan.md` pflegen, Monitoring
und Bericht, Statusauskünfte.
Nicht zuständig: Upload (macht der Mensch), außerplanmäßige Uploads, die Nische
(nur vorschlagen).

## Wo was steht
- Ablauf im Detail → `skills/pipeline`
- Heartbeat-Checks → `HEARTBEAT.md`
- Analyse/Report → `skills/monitorreport`
- Rezept anlegen/aktivieren → `skills/recipebuilder`
- Befehle, Pfade, Env → `TOOLS.md`
- Inhaltswissen → `recipes/<name>.md`
