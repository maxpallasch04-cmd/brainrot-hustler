---
name: ytclip
description: "Ein langes YouTube-Video (Sport) herunterladen, mit einem Vision-Modell ein Format (Scoreboard + Hauptgeschehen) bestimmen und daraus vertikale Clips schneiden."
---

# YT-Clip

Prozess, um aus einem langen YouTube-Video vertikale Clips zu machen.
Nische, Quellen, Kriterien und Ton kommen aus dem Rezept `recipes/<name>.md`
(mit `art: YT-Clip`).

**Aufruf:** aus `pipeline` Schritt 3 (über das `art` des Rezepts). Alles
YT-Spezifische steht hier — die Pipeline ist generisch.

## Kerngedanke

- **Ein Format pro Video** (nicht pro Kanal): Scoreboard + Hauptgeschehen werden
  für genau dieses Video bestimmt und für **alle** seine Clips wiederverwendet.
- Zweistufig: das **Vision-Modell erkennt** die Boxen in 4 Screenshots (nur
  Koordinaten, kein OCR) — das **normale Modell baut daraus zusammen mit dem
  Rezept** das Format: welche Boxen relevant sind, Reihenfolge, 9:16-Mapping.
- Das Format wird **einmal pro Video** bestimmt und für **alle** seine Clips genutzt.
- Ein Video kann über mehrere Läufe abgearbeitet werden. Der Zustand liegt in
  `data/brainrot.db` (`yt_source`, `yt_clip`, siehe `yt_clips/README.md`).

## Ablauf

1. **Rezept laden** (`recipes/<name>.md`) — legt fest, welche Videos in Frage
   kommen und was einen clipwürdigen Moment ausmacht.
2. **Offene Arbeit prüfen:**
   ```
   python3 -m yt_clips.cli next
   ```
   Die `action` sagt, was zu tun ist: `format` | `clip` | `find` | `download`.
   **Immer `next` fragen** — nie parallel dieselben Clips rendern.

### `format` — Video noch ohne Format (zweistufig)

   a. **4 Screenshots**, gleichmäßig über das Video verteilt (nicht am
      Anfang, sonst wird z. B. eine Halbzeit-Vollbildgrafik als „Layout" erkannt):
      ```
      python3 -m video_generation.cli frames --in <pfad> --count 4 --out-dir frames --width 1280
      ```
   b. **Stufe 1 — grobe Boxen:** die 4 Bilder mit dem Vision-Modell ansehen → es
      liefert **Boxen** `(x, y, w, h)` für die erkennbaren Bereiche (Scoreboard,
      Action, weitere). Das Vision-Modell **erkennt nur**, es entscheidet nicht.
   c. **Stufe 2 — Unterboxen:** die große Score-Box **croppen + hochskalieren** und
      **nur diesen Ausschnitt** nochmal ins Vision-Modell geben (Schrift wird so
      lesbar):
      ```
      python3 -m yt_clips.cli crop-frame --in frames/<bild>.png --box <score-box> --out sb.png --scale 2
      ```
      Es liefert die **Unterboxen** (Name, Score, Liste …) — Koordinaten **relativ
      zum Crop**. Zurückrechnen mit dem `offset` aus der Ausgabe
      (`unterbox + offset`, bei `--scale` vorher durch den Faktor teilen).
   d. **Format bauen** — mit dem **normalen (Text-)Modell**, **zusammen mit dem
      Rezept**: **welche Boxen relevant sind**, Reihenfolge und 9:16-Mapping stehen
      im Rezept (`## Format`), nicht hier. Jede Region bekommt einen **`name`**
      (z. B. `scoreboard`, `action`) — damit lässt sie sich pro Clip an-/abwählen.
   e. Ergebnis speichern (Format = Regions-Liste für `video_generation layout`):
      ```
      python3 -m yt_clips.cli format-set --source <id> --regions fmt.json
      ```

### `find` — clipwürdige Stellen finden

   **Automatisch:** Kapitel + Audio-Peaks erkennen —
   laut = Jubel/Kommentator. Kein Vision-Modell, keine API-Kosten.
   ```
   python3 -m yt_clips.cli highlights --source <id> --top 10 --add
   ```
   Die Kandidaten (`reason` sagt warum: „Kapitel: …" oder „Lautheit …") einmal
   überfliegen, unpassende streichen (`status: Skipped`).

   **Zahlen im Transkript (Schnitt-Anker, Hauptweg):** Die Bewertungen werden
   angesagt, und an jeder Vergabe ist der Score im Scoreboard sichtbar → **Schnitte
   am Score setzen**. Zahlen im Transkript suchen; **OCR nur zur Kontrolle**
   (selten, lokal) auf der Score-Box:
   ```
   python3 -m subtitles.cli numbers --in <transcript.vtt> --min 6 --max 10
   ```
   Schnitte nur, wo das **Scoreboard sichtbar** ist. Die **Offset-Tendenz**
   (früher/später relativ zum Score), die **Score-Schwelle** und die **Phase**
   stehen im Rezept (`## Clips`,`## Format`) — nicht hier.

### `clip` — einen Kandidaten rendern

   ```
   python3 -m yt_clips.cli clip --clip <clip-id> --out out.mp4 --size 1080x1920 --used
   ```
   Setzt das gespeicherte Format als `regions` ein (Scoreboard + Action) und
   schneidet `start`–`end`. Danach ist der Clip `Used`; ist nichts mehr übrig,
   wird das Video `Exhausted`.
   - **Auswahl pro Clip (Hybrid):** 1 Frame aus dem Clip ansehen und nicht
     vorhandene Boxen abwählen (Region-`name`):
     ```
     python3 -m yt_clips.cli clip --clip <id> --out out.mp4 --drop scoreboard --used
     ```
     `--only a,b` / `--drop a,b` filtern die benannten Regionen. Der
     **Score-Bereich** wird erstmal **immer** mitgezeigt (Rezept kann das ändern).
   - **Fallback:** passt kein bekanntes Layout (Studio/Halbzeit) → 4 Frames **aus
     dem Clip** → wie unter `format` neu erkennen → per Clip speichern:
     `python3 -m yt_clips.cli format-set --clip <id> --regions fmt.json`
     (überschreibt die Quelle).

### `download` — neues Video

   Kein offenes Video mehr → neues laden (das Rezept bestimmt die Quelle).
   Transcript gleich mitnehmen, wenn das Rezept Untertitel braucht:
   ```
   python3 -m yt_clips.cli download --url <url> --out-dir clips --recipe <name> --subs-lang en
   ```
   Danach wieder bei `format` beginnen.

### Untertitel (falls das Rezept sie will)

   **Nach dem Rendern.** Transcript-Pfad steht in `next`/`list` (`subs_path`).
   Untertitel bleiben ein eigenes Artefakt — Fenster schneiden, dann einbrennen:
   ```
   python3 -m subtitles.cli cut  --in <transcript.vtt> --start <start> --end <end> --out clip.srt
   python3 -m subtitles.cli burn --in out.mp4 --subs clip.srt --out final.mp4 \
       --font-size 64 --margin-v 220 --outline 3
   ```
   Denselben Text auch für **Titel/Beschreibung/Hashtags** nutzen (Trick, Skater).

## Übergabe an die Pipeline

- Ziel des Aufrufs: **genau eine** fertige `.mp4` (ein Plan-Eintrag = ein Video).
- **Kontext zurückgeben:** `source`-id, `start`/`end`, `reason` — die Pipeline
  braucht ihn für Titel/Beschreibung und die Erfassung.
- **Pausieren ist normal:** `download` (langes Video) und `format`
  (Vision-Bestätigung) laufen nicht in einem Shot. Später hier fortsetzen.
- **Plan-Eintrag:** erst wenn ein Highlight gewählt ist, den Eintrag für dieses
  Video anlegen/ergänzen und die Idee setzen (z. B. „Tor, 78. Minute") — vorher
  steht der Highlight ja nicht fest.
- Danach **prüfen** (`probe` → 9:16, Höhe ≥ 1280) und an die Pipeline zurückgeben.

## Hinweise

- CLI bevorzugen; die Python-API nur in größeren Skripten.
- Das Vision-Modell liefert **Koordinaten**, nicht Text. 
- Fensterbreite der Kandidaten (z. B. „Peak − 8 s, 20 s lang") variiert pro Sport
  und gehört ins Rezept (`Auswahl`).
