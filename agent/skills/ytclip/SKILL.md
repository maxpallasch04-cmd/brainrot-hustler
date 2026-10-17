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
  Die Score-Box ist **statisch** (Koordinaten fix) — pro Clip kein Re-Detect.
- Zweistufig: das **Vision-Modell erkennt** die Boxen in 4 Screenshots (nur
  Koordinaten, kein OCR) — das **normale Modell baut daraus zusammen mit dem
  Rezept** das Format: welche Boxen relevant sind, Reihenfolge, 9:16-Mapping.
- Ein Video kann über mehrere Läufe abgearbeitet werden. Der Zustand liegt in
  `data/brainrot.db` (`yt_source`, `yt_clip`, siehe `yt_clips/README.md`).

## Ablauf

1. **Rezept laden** (`recipes/<name>.md`) — legt fest, welche Videos in Frage
   kommen und was einen clipwürdigen Moment ausmacht.
2. **Offene Arbeit prüfen:**
   ```
   ~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli next
   ```
   Die `action` sagt, was zu tun ist: `format` | `clip` | `find` | `download`.
   **Immer `next` fragen** — nie parallel dieselben Clips rendern.

### `format` — Video noch ohne Format (zweistufig)

   a. **4 Screenshots**, gleichmäßig über das Video verteilt (nicht am
      Anfang, sonst wird z. B. eine Halbzeit-Vollbildgrafik als „Layout" erkannt):
      ```
      ~/.openclaw/workspace-brainrothustler/bin/cli video_generation.cli frames --in <pfad> --count 4 --out-dir frames --width 1280
      ```
   b. **Stufe 1 — grobe Boxen:** die 4 Bilder mit dem Vision-Modell ansehen → es
      liefert **Boxen** `(x, y, w, h)` für die erkennbaren Bereiche (Scoreboard,
      Action, weitere). Das Vision-Modell **erkennt nur**, es entscheidet nicht.
   c. **Stufe 2 — Unterboxen:** die große Score-Box **croppen + hochskalieren** und
      **nur diesen Ausschnitt** nochmal ins Vision-Modell geben (Schrift wird so
      lesbar):
      ```
      ~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli crop-frame --in frames/<bild>.png --box <score-box> --out sb.png --scale 2
      ```
      Es liefert die **Unterboxen** (Name, Score, Liste …) — Koordinaten **relativ
      zum Crop**. Zurückrechnen mit dem `offset` aus der Ausgabe
      (`unterbox + offset`, bei `--scale` vorher durch den Faktor teilen).
      Die Unterboxen als **`boxes`** in Quellkoordinaten speichern (`score`,
      `name`, `list` …). **`boxes.score` ist die Anzeige- UND OCR-Box** — nicht das
      ganze Scoreboard.
   d. **Format bauen** — mit dem **normalen (Text-)Modell**, **zusammen mit dem
      Rezept**: **welche Boxen relevant sind**, Reihenfolge und 9:16-Mapping stehen
      im Rezept (`## Format`), nicht hier. Jede Region bekommt einen **`name`**
      (z. B. `scoreboard`, `action`) — damit lässt sie sich pro Clip an-/abwählen.
      - **Score statt Gesamtboard:** Nur die **`score`-Unterbox** rendern (Band
        oben, volle Breite, Richtwert 200–400 px hoch), **nie `scoreboard` als
        Ganzes**. `name`/`list` optional als schmale Bänder. Die rohe
        `boxes.score` (Quellkoordinaten) bleibt für OCR erhalten. Die Box ist
        pro Video **fix**; pro Clip nur OCR (leer vs. Score), kein Re-Detect.
      - **Lückenlos:** Die Regionen füllen die Ausgabefläche ohne schwarze Balken
        (Hauptbox volle Breite, Rest für die Nebenboxen). `fit: cover`, **nicht
        `stretch`**. Die CLI prüft das bei `format-set`/`clip` und gibt
        `warnings` zurück (Lücken, Überlauf, `contain`, zu kleine/abgeschnittene
        Score-Box) — Warnungen ernst nehmen und das Format korrigieren.
      - **Action-Box:** Der Fahrer/Akteur bleibt in **jedem** geprüften Frame
        vollständig in der Box, an **jeder Seite ≥ 10 % Rand**. 3–5 Frames aus dem
        Trick-/Run-Fenster prüfen. Berührt er den Rand → Box **vergrößern** oder
        **pro Clip** neu erkennen (`format-set --clip`).
   e. Ergebnis speichern (Format = Regions-Liste für `video_generation layout`):
      ```
      ~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli format-set --source <id> --regions fmt.json
      ```

### `find` — clipwürdige Stellen finden

   **Hauptweg — Score als Such-Anker, Trick als Start-Anker:** Die Bewertung wird
   angesagt und im Scoreboard angezeigt. Die **Ansage kann 30–60 s nach dem Trick**
   liegen → **nie als Startanker** nehmen. Erst den **Anzeige-Beginn** bestimmen
   (Transkript-Zahlen für die Ansage, OCR auf `boxes.score` für die Einblendung),
   dann das Fenster **rückwärts bis zum Trick-/Run-Beginn** bauen. Zahlen im
   Transkript:
   ```
   ~/.openclaw/workspace-brainrothustler/bin/cli subtitles.cli numbers --in <transcript.vtt> --min 6 --max 10
   ```

   **Score-Anzeige per OCR (fest, günstig):**
   ```
   ~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli ocr --clip <id> --step 1
   ```
   Liest die feste `boxes.score` (kein per-Clip-Re-Detect), gibt Werte
   **0.0–10.0** und `first_stable` (≥ 2 Treffer) + `runs` aus. Leere Frames
   werden ignoriert. `first_stable` ist der **End-Anker**, nicht die Ansage.
   Treffer als Kandidaten eintragen — mit **Score-Anker + `pre_roll`** (die CLI
   rechnet Start/Ende):
   ```json
   [{"score": 326.0, "pre_roll": 20, "post_roll": 3, "reason": "Best Trick"}]
   ```
   ```
   ~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli candidates-add --source <id> --json cands.json
   ```
   `pre_roll`: Best Trick **≥ 10 s** (besser 15), Lines = **Run-Länge**. Die CLI
   warnt bei `pre_roll < 8 s` („nur Feier") und bei Fenstern < 5 s. Unpassende
   streichen (`status: Skipped`). Schnitte nur, wo das **Scoreboard sichtbar** ist.

   **A oder B:** Reicht ein Fenster nicht (der Score kommt später), zwei
   Segmente — Trick + Score:
   ```json
   [{"segments": [{"start": 305, "end": 316}, {"start": 324, "end": 330}],
     "reason": "Trick + Score"}]
   ```
   `clip` rendert die Segmente einzeln und hängt sie **hart** aneinander;
   `only`/`drop` pro Segment überschreiben die globale Auswahl.
   **Schnittkanten:** Beide Segmentkanten vorher mit `subtitles.cli snap` auf
   Satz-/Wortgrenzen legen (Start `before`, Ende `after`) — Trick-Fenster endet
   nach der Landung, Score-Fenster beginnt vor der Einblendung. **Nie mitten in
   einen Kommentatorsatz schneiden**, auch nicht am Übergang Trick → Score.

   **Zusatzsignal (optional, kostenlos): Kapitel + Audio-Peaks** — laut = Jubel/
   Kommentator. Als günstige Vorauswahl ergänzend zum Score nutzen; kein
   Vision-Modell, keine API-Kosten:
   ```
   ~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli highlights --source <id> --top 10 --add
   ```
   Die Kandidaten (`reason` sagt warum: „Kapitel: …" / „Lautheit …") überfliegen,
   unpassende streichen (`status: Skipped`).

   **Phase — Lines oder Best Trick:** *wie* ein Clip erkannt wird (welche Phase,
   Score-Schwelle, Länge, Offset-Tendenz) steht im Rezept (`## Auswahl`,
   `## Clips`) — nicht hier. Aktive YT-Rezepte: `recipes/ytsls-bestline.md`
   (Lines) und `recipes/ytsls-besttrick.md` (Best Trick).

### `clip` — einen Kandidaten rendern

   ```
   ~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli clip --clip <clip-id> --out out.mp4 --size 1080x1920 --used
   ```
   Setzt das gespeicherte Format als `regions` ein (Scoreboard + Action) und
   schneidet `start`–`end`. Danach ist der Clip `Used`; ist nichts mehr übrig,
   wird das Video `Exhausted`.
   - **Auswahl pro Clip (Hybrid):** 1 Frame aus dem Clip ansehen und nicht
     vorhandene Boxen abwählen (Region-`name`):
     ```
     ~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli clip --clip <id> --out out.mp4 --drop scoreboard --used
     ```
     `--only a,b` / `--drop a,b` filtern die benannten Regionen. Der
     **Score-Bereich** wird erstmal **immer** mitgezeigt (Rezept kann das ändern).
   - **`warnings` prüfen:** Die Ausgabe meldet Lücken/Überlauf im Layout. Bei
     einer Lücke zuerst das Format korrigieren (nicht den Clip als fertig
     ansehen).
   - **Fallback:** passt kein bekanntes Layout (Studio/Halbzeit) → 4 Frames **aus
     dem Clip** → wie unter `format` neu erkennen → per Clip speichern. Nur bei
     echtem Layout-Wechsel, **nicht fürs Scoreboard** (die Box ist fix):
     `~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli format-set --clip <id> --regions fmt.json`
     (überschreibt die Quelle).

### `download` — neues Video

   Kein offenes Video mehr → neues laden (das Rezept bestimmt die Quelle).
   Transcript gleich mitnehmen, wenn das Rezept Untertitel braucht:
   ```
   ~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli download --url <url> --out-dir clips --recipe <name> --subs-lang en
   ```
   Danach wieder bei `format` beginnen.

   **Cookies:** YouTube blockt Rechenzentrums-IPs (Bot-Schutz) — der Download
   braucht eine angemeldete Session. Die Cookies liegen meist schon als
   `~/.openclaw/state/brainrot/cookies.txt` (Details/Alternativen:
   `modules/yt_clips/README.md` → Cookies). Fehlt der Bot-Check-Hinweis nicht,
   meldet der Download genau, was zu tun ist.

### Untertitel (falls das Rezept sie will)

   **Nach dem Rendern.** Transcript-Pfad steht in `next`/`list` (`subs_path`).
   Untertitel bleiben ein eigenes Artefakt — Fenster schneiden (an der
   **Satzgrenze**), dann einbrennen:
   ```
   ~/.openclaw/workspace-brainrothustler/bin/cli subtitles.cli cut  --in <transcript.vtt> --start <start> --end <end> --snap sentence --text --out clip.srt
   ~/.openclaw/workspace-brainrothustler/bin/cli subtitles.cli burn --in out.mp4 --subs clip.srt --out final.mp4 \
       --font-size 64 --margin-v 220 --outline 3
   ```
   Denselben Text (`text` aus `cut`) für **Titel/Beschreibung/Hashtags** nutzen
   (Trick, Skater).

   **Token-Regel:** Das VTT **nie** komplett lesen. `cut --snap sentence` liefert
   nur die angepassten Zeiten + kurzen Text. Für einen unklaren Moment:
   `subtitles.cli words --at <t> --window 3` (nur ~10–30 Wörter). `snap` für eine
   einzelne Grenze. Alles andere bleibt in der Datei.

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
