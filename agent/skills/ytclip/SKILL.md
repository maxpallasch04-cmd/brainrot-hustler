---
name: ytclip
description: "Ein langes YouTube-Video herunterladen, mit einem Vision-Modell ein Format bestimmen und daraus vertikale Clips schneiden."
---

# YT-Clip

Prozess, um aus einem langen YouTube-Video vertikale Clips zu machen.

**Aufruf:** aus `pipeline` Schritt 3 (über das `art` des Rezepts). Alles
YT-Spezifische steht hier — die Pipeline ist generisch.

## Kerngedanke

- Identische Positionierungen (Boxes) **nur einmal pro Roh-Video erkennen**
  (nicht pro Clip); diese Boxen werden im Rezept benannt.
- Ein Video kann über mehrere Läufe abgearbeitet werden. Der Zustand liegt in
  `memory/brainrot.db` (`yt_source`, `yt_clip`, siehe `yt_clips/README.md`).

## Ablauf

1. **Rezept laden** (`recipes/<name>.md`) — legt fest, welche Videos in Frage
   kommen und was einen clipwürdigen Moment ausmacht.
2. **Offene Arbeit prüfen:**
   ```
   ~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli next --recipe <recipe>
   ```
   Die `action` sagt, was zu tun ist: `clip` | `find` | `download`. Das Rezept
   ist der Queue-Schlüssel — fremdes Material taucht hier nicht auf.
   **Immer `next` fragen** — nie parallel dieselben Clips rendern.

### `format` — Rohvideo noch ohne Boxen

   a. **5 Screenshots**, gleichmäßig über das Video verteilt (nicht am
      Anfang, sonst wird z. B. eine Halbzeit-Vollbildgrafik als „Layout" erkannt):
      ```
      ~/.openclaw/workspace-brainrothustler/bin/cli editor.cli frames --in <pfad> --count 5 --out-dir memory/screenshots --width 1280
      ```
   b. **Boxen erkennen:** die 5 Bilder mit `view_image` ansehen → es liefert
      **Boxen** `(x, y, w, h)` für die erkennbaren Bereiche.

   c. **Unterboxen** (wenn gefragt): die große Box **croppen + hochskalieren**:
      ```
      ~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli crop-frame --in memory/screenshots/<bild>.png --box <score-box> --out memory/screenshots/sb.png --scale 2
      ```
      **Nur diesen Ausschnitt** nochmal ins Vision-Modell geben. Koordinaten sind
      **relativ zum Crop**: zurückrechnen mit dem `offset` aus der Ausgabe
      (`unterbox + offset`, bei `--scale` vorher durch den Faktor teilen).
   d. **Boxen speichern** (einmal pro Video, kanonisch in der DB):
      ```
      ~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli boxes-set --source <id> --json boxes.json
      ```
      Form: `{"score": [x,y,w,h], "name": [...]}` — in **Quellkoordinaten**.

### `find` — clipwürdige Stellen finden

   Wonach du suchst, steht im Rezept (`## Auswahl`, `## Clips`). Das sind die
   Werkzeuge dafür:

   1. **Audio-Peaks + Kapitel** (grobe Kandidaten, ohne Vision):
      ```
      ~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli highlights --source <id> --top 10 --add
      ```
      `--add` schreibt die Treffer direkt als Kandidaten in die DB.
   2. **Transkript-Zahlen** (Score-Ansage als Suchanker):
      ```
      ~/.openclaw/workspace-brainrothustler/bin/cli editor.cli subtitles numbers --in <subs.vtt> --min 6 --max 10
      ```
   3. **Bestimmte Transkript-Zeilen lesen** — immer nur ein Fenster, nie die
      ganze Datei (Pfad: `subs_path` aus `next`/`list`):
      ```
      ~/.openclaw/workspace-brainrothustler/bin/cli editor.cli subtitles words --in <subs.vtt> --at <t> --window 3
      ```
      Schnittkanten: `editor.cli subtitles snap --in <subs.vtt> --at <t> --mode sentence --direction before` (bzw. `after`).
   4. **Score-Anzeige per OCR** (feste Box, günstig):
      ```
      ~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli ocr --clip <id> --box <x,y,w,h> --step 1
      ```
      Liefert Werte `0.0–10.0`; `first_stable` ist der **End-Anker**, nicht die Ansage.
   5. **Bewegung messen** (Start-Anker):
      ```
      ~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli motion --source <id> --from <t> --to <t>
      ```
      `first_motion` = erster wirklich bewegter Frame (nicht aus dem Transkript raten).

   Kandidaten eintragen — als Fenster oder als Score-Anker:
   ```
   ~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli candidates-add --source <id> --json cands.json
   ```
   Form: `[{"start":..,"end":..,"reason":".."}]` oder
   `[{"score":..,"pre_roll":..,"post_roll":..,"reason":".."}]`.

### `clip` — einen Kandidaten rendern

   Die **Action-Box wird pro Clip bestimmt** — deshalb gehört sie nicht in
   `format`: der Akteur bewegt sich, die Kamera wechselt.

   a. **2–3 Frames aus dem Fenster** ansehen (nicht aus dem ganzen Video):
      ```
      ~/.openclaw/workspace-brainrothustler/bin/cli editor.cli frames --in <rohvideo> --at <start>,<mitte>,<ende> --out-dir memory/screenshots --width 1280
      ```
      Box so legen/verschieben, dass der Akteur an **jeder Seite ≥ 10 %** Rand
      hat. Die Box muss **exakt 9:16** sein (Breite = Höhe × 9/16, ganzzahlig),
      sonst schneidet `cover` etwas weg.
   b. **Spec bauen** (Fenster aus dem Kandidaten, `boxes` per
      `yt_clips.cli boxes-get --source <id>` übernehmen):
      ```json
      {
        "size": [1080, 1920], "fps": 30,
        "expect": {"ratio": "error"},
        "boxes": {"score": [1200, 80, 180, 90]},
        "clips": [{
          "source": "memory/clips/<datei>.mp4", "start": 1268, "end": 1301,
          "regions": [
            {"name": "action", "box": [690, 60, 540, 960], "size": [1080, 1920],
             "position": [0, 0], "fit": "cover"},
            {"name": "scoreboard", "box": [40, 20, 360, 900], "size": [320, 800],
             "position": [730, 60], "fit": "contain"}
          ]
        }]
      }
      ```
   c. **Prüfen, rendern, markieren:**
      ```
      ~/.openclaw/workspace-brainrothustler/bin/cli editor.cli validate --spec memory/specs/<name>.json
      ~/.openclaw/workspace-brainrothustler/bin/cli editor.cli render   --spec memory/specs/<name>.json --out memory/videos/<name>.mp4 --overwrite
      ~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli used   --clip <clip-id>
      ```
      Ist nichts mehr übrig, wird das Video `Exhausted`.
   - **`warnings` prüfen:** `validate` meldet Lücken/Überlauf im Layout. Bei
     einer Lücke zuerst die Spec korrigieren.
   - **Auswahl pro Clip:** nicht gewünschte Regionen einfach in der Spec weglassen.

### `download` — neues Video

   Kein offenes Video mehr → neues laden. Transcript gleich mitnehmen:
   ```
   ~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli download --url <url> --out-dir memory/clips --recipe <name> --subs-lang en
   ```
   Der Transcript-Pfad landet in `subs_path` (sichtbar in `next`/`list`).
   Danach wieder bei `find`.

## Übergabe an die Pipeline

- Abschluss des Skills, sobald `clip` vollständig ausgeführt wurde.
- **Kontext zurückgeben:** `source`-id, `start`/`end`, `reason` — die Pipeline
  braucht ihn für Titel/Beschreibung und die Erfassung.
- **Pausieren ist normal:** `download` (langes Video) und `format`
  (Vision-Bestätigung) laufen nicht in einem Shot. Später hier fortsetzen.
- **Plan-Eintrag:** Der Eintrag existiert schon (`add-plan`). Erst wenn ein
  Highlight gewählt ist, ihn abschließen:
  `longterm_memory.cli generated <id> --title ... --description ... --file memory/videos/<name>.mp4 --len-s <s>`.

## Hinweise

- CLI bevorzugen; die Python-API nur in größeren Skripten.
- Bei Unsicherheit: `next --recipe <recipe>`.
- Das Vision-Modell liefert **Koordinaten**, nicht Text.
- Fensterbreite der Kandidaten (z. B. „Peak − 8 s, 20 s lang") variiert pro Sport
  und gehört ins Rezept (`Auswahl`).
