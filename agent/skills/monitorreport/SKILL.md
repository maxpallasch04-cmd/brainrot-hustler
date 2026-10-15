---
name: monitorreport
description: "Erstellt den täglichen TikTok-Content-Report: Metriken analysieren, interpretieren, per Telegram senden."
---

# Monitoring-Report

Ablauf für die tägliche Contentanalyse des Kanals. Analysiert und berichtet nur —
ändert weder den Plan noch die Nische (Nischen-Anpassung bleibt manuell).

Modul-Doku: `monitoring/README.md`, `longterm_memory/README.md`.

## Ablauf

1. **Report bauen.** Die neuesten Videos des Kanals holen, mit dem Langzeitgedächtnis
   abgleichen, den Report berechnen, speichern und die frischen Metrik-Schnappschüsse
   anhängen.
   ```
   python3 -m monitoring.cli analyze --max 50
   ```
   JSON-Felder: `N`, `G`, `d_global`, `V_0`, `V_1`, `d_video`, `blowups`,
   `unmatched`.
2. **Interpretieren.** Den Report gegen das Langzeitgedächtnis lesen
   (`longterm_memory.cli get-video <id>` / `list-videos`), um `d_video` /
   `d_global` auf `art`, `recipe`, `theme`, Wortwahl (Titel/Beschreibung) und Länge
   jedes Videos zurückzuführen. Benennen, was lief und was nicht — der Schnitt pro
   Rezept ist am aussagekräftigsten.
3. **Formatieren** — eine kurze Telegram-Nachricht: Kennzahlen (`N`, `G`,
   `d_global`, bester/schlechtester `d_video`, `blowups`) plus Interpretation und
   einen konkreten Vorschlag.
4. **Senden** per Telegram an die Empfänger (siehe `AGENTS.md` → „Empfänger").
   Keine Antwort erwartet.

## Hinweise

- Auth: der gespeicherte TikTok-Token erneuert sich automatisch. Schlägt `analyze`
  mit Auth-/Token-Fehler fehl, den einmaligen Flow (`monitoring.cli login`, siehe
  README) ausführen und erneut versuchen.
- Kommentar-*Text* ist nicht verfügbar (nur `comment_count`) — die Wortwahl-Analyse
  nutzt Titel/Beschreibungen, keine Kommentare.
- `analyze` berechnet **und** persistiert (Report-Zeile + neue Schnappschüsse).
  Einmal pro Fenster ausführen, nicht für dasselbe Fenster wiederholen.
- Optional Blow-up-Erkennung: `--no-blowup` überspringt sie.
- Läuft täglich per Cron; Timing/Reihenfolge steht in `AGENTS.md`.
