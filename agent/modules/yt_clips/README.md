# yt_clips

Zustand und Analyse für die **YT-Clip**-Art: aus einem langen YouTube-Video
werden mehrere vertikale Clips. Das Modul **rendert nicht** und kennt kein
Layout - es liefert Fenster, Boxen und Messwerte; das Video schreibt `editor`.

## Zustand

- `yt_source.status`: `Downloaded` (offen, suchen/clippen) oder `Exhausted`
  (bewusst abgeschlossen, kein `find` mehr).
- `yt_clip.status`: `Candidate` → `Used` / `Skipped`.
- Ein verbrauchter oder geskippter Clip beendet die Quelle **nicht**. Erst
  `exhaust` schließt sie; neue `candidates-add` öffnen sie wieder.
- `next` bietet `find` so lange an, wie die Quelle offen ist und kein
  `Candidate` wartet - ein Video wird über mehrere Läufe abgearbeitet.

## Rezept als Queue-Schlüssel

Jede Quelle trägt ein `recipe` (beim `download` gesetzt, nachtragbar per
`recipe-set`). `next` verlangt ein Rezept und sieht nur dessen Quellen - so
mischt sich kein fremdes Material in eine andere Art.

## CLI

```
bin/channel <id> yt_clips.cli next --recipe <name>              # clip | find | download
bin/channel <id> yt_clips.cli download --url <url> --recipe <name> [--out-dir <dir>] [--subs-lang en]
bin/channel <id> yt_clips.cli recipe-set --source <id> --recipe <name>

bin/channel <id> yt_clips.cli highlights --source <id> --top 10 [--add]
bin/channel <id> yt_clips.cli candidates-add --source <id> --json <file|-> 
bin/channel <id> yt_clips.cli candidates-list --source <id> [--status Candidate]
bin/channel <id> yt_clips.cli used --clip <id> [--video-id <id>]
bin/channel <id> yt_clips.cli skip --clip <id>
bin/channel <id> yt_clips.cli exhaust --source <id>
bin/channel <id> yt_clips.cli reopen  --source <id>

bin/channel <id> yt_clips.cli boxes-set --source <id> --json <file>
bin/channel <id> yt_clips.cli boxes-get --source <id>
bin/channel <id> yt_clips.cli crop-frame --in <png> --box <x,y,w,h> --out <png> [--scale 2]

bin/channel <id> yt_clips.cli motion --clip <id>
bin/channel <id> yt_clips.cli motion --source <id> --from <s> --to <s>
bin/channel <id> yt_clips.cli ocr --clip <id> --box <x,y,w,h> [--step 1]
bin/channel <id> yt_clips.cli ocr --source <id> --box <x,y,w,h> --from <s> --to <s>

bin/channel <id> yt_clips.cli list [--recipe <name>]
```

Alle Befehle geben JSON aus. Der Prozess (welche Analyse wann) steht in
`skills/ytclip`.

## Boxen

Die Unterboxen aus der Vision (`score`, `name`, …) liegen **einmal pro Quelle**
im Store, kanonisch in Quellkoordinaten. `next`/`list` geben sie als `boxes` mit.
Die Spec kopiert, was sie braucht; `ocr` liest sie **nicht** aus der DB, sondern
bekommt `--box` vom Aufrufer.

## Format (Spec für `editor`)

```json
{"size": [1080, 1920], "background": "#000000",
 "boxes": {"score": [120, 30, 220, 80]},
 "regions": [
   {"name": "action", "box": [440, 0, 607, 1080], "size": [1080, 1920],
    "fit": "cover", "position": "center"},
   {"name": "scoreboard", "box": [80, 10, 340, 900], "size": [320, 848],
    "fit": "contain", "position": [740, 40]}
 ]}
```

- **Action:** eine Box pro Clip, die den Akteur über alle Kameras enthält -
  9:16 in voller Quellhöhe (`Breite = Höhe × 9/16`), `fit: cover`, zentriert.
  Breitere Boxen werden beschnitten, `contain` erzeugt Balken.
- **Scoreboard:** vertikale Kachel in einer Ecke (`contain`, ≈ 25-35 % der
  Ausgabebreite), kein Band über die volle Breite.
- `boxes` wird vom Editor ignoriert - es ist der OCR-Anker.
- Welche Regionen ein Clip zeigt, entscheidet die Spec: nicht gewünschte
  einfach weglassen.

## OCR (Score)

Liest die feste Score-Box (keine per-Clip-Erkennung), Werte `0.0-10.0`.
Engine ist **Tesseract** (`--engine rapidocr` als optionaler Fallback).

Ausgabe: `first`, `first_stable`, `runs`, `checked`, `empty`. `first_stable` ist
der **End-Anker** für einen Score-Clip, nicht die Ansage.

## Motion (Start-Anker)

Frame-Differenzen lokal (MoviePy + NumPy), `--fps` (Default 4), `--width`
(Default 160), `--threshold` adaptiv. Ausgabe: `first_motion`, `last_motion`,
`moving_ratio`, `segments`.

`first_motion` ist der **Start-Anker** (minus ~2 s Anlauf), nicht die Ansage.

## Kandidaten

```json
[{"start": 1200.0, "end": 1235.0, "reason": "Tor"}]
[{"score": 326.0, "pre_roll": 20, "post_roll": 3, "reason": "Best Trick"}]
[{"segments": [{"start": 305, "end": 316}, {"start": 324, "end": 330}], "reason": "Trick + Score"}]
```

`score` ist die **Einblendung**, nicht die Ansage (die liegt oft 30-60 s später).
`pre_roll` muss den Trick enthalten (Best Trick mindestens 10 s). `candidates-add`
warnt bei `pre_roll < 8 s` und bei Fenstern unter 5 s. Zwei Fenster (`segments`)
werden beim Rendern hart aneinandergehängt; Kanten vorher mit
`editor.cli subtitles snap` auf Satzgrenzen legen.

## Untertitel

`download --subs-lang en` holt das Transcript mit (`subs_path` am Source).
Fenster schneiden und Einbrennen macht `editor` (`subtitles`).

## Zugänge

Cookies, Proxy und Extraktor-Optionen für YouTube stehen in der Projekt-README
(Abschnitt „Zugänge"). Ohne Cookies scheitert der Download auf Rechenzentrums-IPs.
