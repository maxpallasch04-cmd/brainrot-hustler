---
name: cliptwitch
description: "Twitch-Clips finden, herunterladen und zu einem gerenderten vertikalen Video schneiden."
---

# Twitch-Clip

Wiederverwendbarer Ablauf, um Twitch-Clips in ein fertiges, gerendertes Video zu
verwandeln.

Zugangsdaten kommen aus der Umgebung (`TWITCH_CLIENT_ID` /
`TWITCH_CLIENT_SECRET`); `download` braucht keine. Modul-Doku:
`twitch_clips/README.md`, `video_generation/README.md`.

## Ablauf

1. **Kategorie auflösen.** Twitch hat keine Volltextsuche, also zuerst nach
   Kategorie (oder Broadcaster) eingrenzen.
   ```
   ~/.openclaw/workspace-brainrothustler/bin/cli twitch_clips.cli game-id --name "<Game>"
   ```
2. **Gerankte Shortlist bauen.** Ergebnisse kommen meistgesehen zuerst; clientseitig
   ranken.
   ```
   ~/.openclaw/workspace-brainrothustler/bin/cli twitch_clips.cli clips --game "<Game>" --hours 168 --min-views 5000 \
       --top 10 --sort velocity --state data/twitch_seen.json
   ```
   - `--sort views` = bewährte Hits, `--sort velocity` = frisch viral (views/hour).
     Clips brauchen Tage, um viral zu gehen → lieber `--hours` weiten als große
     24-h-Zahlen zu erwarten.
   - `--state` hält ein JSON-Set gesehener IDs, sodass wiederholte Läufe nur neue
     Clips zeigen.
3. **Auswählen** — die Clips aus der JSON-Shortlist.
4. **Herunterladen** (keine Zugangsdaten; vorhandene Dateien werden übersprungen,
   außer `--overwrite`).
   ```
   ~/.openclaw/workspace-brainrothustler/bin/cli twitch_clips.cli clips ... \
     | ~/.openclaw/workspace-brainrothustler/bin/cli twitch_clips.cli download --from-json - --out-dir clips
   ```
   oder `download --id <clip-id>` / `--url <clip-url>`. Dateien landen in
   `clips/<clip-id>.mp4`.
5. **Schneiden und bearbeiten** über ein `video_generation`-Rezept (ein JSON → ein
   Video): Segment mit `start`/`end` wählen, `background` setzen, `overlays`
   platzieren (Bild an `x`/`y` ab `t` für eine Dauer), `audio` ergänzen. Ziel
   `1080x1920`, Höhe ≥ 1280.
   ```
   ~/.openclaw/workspace-brainrothustler/bin/cli video_generation.cli render --recipe recipe.json
   ```
   (`--recipe -` liest das Rezept von stdin.)
6. **Prüfen** und die Datei an die Pipeline übergeben.

## Hinweise

- CLI bevorzugen; die Python-API nur innerhalb größerer Skripte nutzen.
- Die Input-Details (Auswahl, Background, Musik, Overlays) kommen aus dem Rezept
  `recipes/<name>.md`; dieser Skill trägt nur den Prozess.
