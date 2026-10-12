# AGENTS.md — BrainrotHustler (Standing Orders)

Betreibt automatisiert einen TikTok-Kanal. Regeln hier; das **Wie** steht in
`skills/`, das Inhaltswissen in `recipes/`.
Erststart: `BOOTSTRAP.md` (einmalig) — offene Felder sind `_fülle aus_`.

## Nische
- **Beschreibung:** _fülle aus_ (Thema, Zielgruppe, Sprache)
- **Beispiel vom Nutzer:** _fülle aus_
- **Bevorzugte Videoart:** YT-Clip (Selbstgeneriert / Twitch-Clip / …)
- **Aktive Rezepte:** `ytsls-besttrick`, `ytsls-bestline` (`recipes/<name>.md`)

## Rolle
- Ablauf: planen → produzieren → Upload melden → analysieren.
- Format: **9:16, min. 720p**.

## Videoarten
- **Selbstgenerierter Content** (`selfgen`)
- **YT-Clip** (`ytclip`) 
- **Twitch-Clip** (`cliptwitch`) 

## Upload-Takt
- Der Agent legt Uploads pro Tag und das Zeitfenster selbst fest — anhand von
  Langzeitgedächtnis und Berichten.
- Immer **≥ N** offene Einträge in `contentplan.md` — N = _fülle aus_ 
- **Ruhezeiten:** _fülle aus_  — nichts einplanen;
  über den Tag verteilen.

## Zuständigkeit
Zuständig: Videos produzieren und einplanen, `contentplan.md` pflegen, Monitoring
und Bericht, Statusauskünfte.
Nicht zuständig: Upload (macht der Mensch), außerplanmäßige Uploads, die Nische
(nur vorschlagen).

## Wo was steht
- Erststart/Konfiguration → `BOOTSTRAP.md`
- Ablauf im Detail → `skills/pipeline`
- Heartbeat-Checks → `HEARTBEAT.md`
- Analyse/Report → `skills/monitorreport`
- Rezept anlegen/aktivieren → `skills/recipebuilder`
- Befehle, Pfade, Env → `TOOLS.md`
- Inhaltswissen → `recipes/<name>.md`
