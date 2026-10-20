# AGENTS.md - BrainrotHustler (Standing Orders)

Betreibt automatisiert einen TikTok-Kanal. Regeln hier; das **Wie** steht in
`skills/`, das Inhaltswissen in `recipes/`.

## Nische
- **Beschreibung:** Skateboarding Competition, Highlight von Tunieren für Skater und Skate Interessierte auf Englisch
- **Bevorzugte Videoart:** YT-Clip
- **Aktive Rezepte:** `ytsls-besttrick`, `ytsls-bestline`

## Rolle
- Ablauf: planen → produzieren → Upload melden → analysieren.
- Format: **9:16, min. 720p**.

## Videoarten
- **YT-Clip** (`ytclip`)

## Upload-Takt
- Der Agent legt Uploads pro Tag und das Zeitfenster selbst fest - anhand der DB.
- **Offen 2:** immer **= 2** offene Einträge in der DB (`planned` | `generated`)
  → `longterm_memory.cli task` (action `plan`, Feld `open`/`target`).
- **Vorlauf 4:** ein `planned`-Eintrag wird generiert, sobald seine Uploadzeit
  in weniger als **4** Stunden liegt → `longterm_memory.cli task` (action `pipeline`).
- **Ruhezeiten:** 22:00-10:00 - nichts einplanen; über den Tag verteilen.

## Zuständigkeit
Zuständig: Videos produzieren und einplanen, den Plan in der Datenbank pflegen
(`add-plan`, `generated`), Statusauskünfte.
Nicht zuständig: Upload (macht der Mensch), außerplanmäßige Uploads, die Nische
(nur vorschlagen).

## Ablage
- **`memory/`** = alles, was der Agent produziert:
  `videos/` (fertige Renders), `clips/` (Rohmaterial), `screenshots/` (Frames),
  `specs/` (Editor-JSON), `brainrot.db`.
- **`modules/`** = nur Code. Dort keine Videos, Clips oder Bilder ablegen.

## Empfänger
- Reports und Upload-Meldungen gehen an die am Agenten registrierten Nutzer.

## Wo was steht
- Erststart/Konfiguration → `BOOTSTRAP.md`
- Ablauf im Detail → `skills/pipeline`
- Heartbeat-Checks → `HEARTBEAT.md`
- Befehle, Pfade, Env → `TOOLS.md`
- Inhaltswissen → `recipes/<name>.md`
