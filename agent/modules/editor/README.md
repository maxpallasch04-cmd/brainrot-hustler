# editor

JSON-Spec rein, ffmpeg raus. Ein Render = **ein** ffmpeg-Lauf, kein MoviePy.
Die Spec beschreibt die Aufteilung frei - Anzahl, Größe und Position der
Regionen sind pro Video unterschiedlich, es gibt keine festen Slots.

## CLI

```
bin/channel <id> editor.cli validate --spec <spec.json> [--pretty]
bin/channel <id> editor.cli render   --spec <spec.json> [--out <datei>] [--overwrite]
bin/channel <id> editor.cli render   --spec <spec.json> --dry-run     # nur der Befehl
bin/channel <id> editor.cli probe    --in <video>
bin/channel <id> editor.cli frames   --in <video> --count 4 [--out-dir <dir>] [--width 1280]
bin/channel <id> editor.cli frames   --in <video> --at 60,300,900 [--out-dir <dir>]
bin/channel <id> editor.cli subtitles words   --in <vtt> --at <t> [--window 3]
bin/channel <id> editor.cli subtitles numbers --in <vtt> [--min 6] [--max 10]
bin/channel <id> editor.cli subtitles snap    --in <vtt> --at <t> --mode sentence --direction before|after
bin/channel <id> editor.cli subtitles burn    --video <mp4> --subs <srt> --out <mp4>
```

- `validate` prüft Struktur und Geometrie gegen **genau diese** Spec und gibt
  `errors` / `warnings` aus. Was als Fehler gilt, entscheidet die Spec über
  `expect` - der Validator hat keine eingebaute Meinung zur Aufteilung.
- `render` validiert vorher selbst und bricht bei Fehlern ab.
- Exit-Codes: `0` ok, `1` Validierung fehlgeschlagen, `2` Fehler (Datei/ffmpeg).
- Fortschritt geht nach **stderr** (`[render] 42.0% (12.3/29.4s)`), stdout bleibt JSON.
- `--out` überschreibt `out` aus der Spec; ohne beides ist der Render ein Fehler.

## Spec

```json
{
  "size": [1080, 1920],
  "fps": 30,
  "background": "#000000",
  "transition": 0,
  "expect": {"overlap": "allow", "ratio": "warn"},
  "out": "out.mp4",
  "clips": [
    {
      "source": "input.mp4",
      "start": 1200.0,
      "end": 1235.0,
      "regions": [
        {"box": [656, 0, 607, 1080], "size": [1080, 1920], "position": [0, 0],
         "fit": "cover"},
        {"box": [0, 0, 400, 130], "size": [400, 130], "position": [30, 30],
         "fit": "contain"}
      ],
      "overlays": [
        {"image": "logo.png", "position": [900, 1700], "size": [120, 120],
         "start": 0.5, "duration": 3.0, "opacity": 1.0}
      ]
    }
  ]
}
```

### Felder

| Feld | Bedeutung |
| --- | --- |
| `size` | Ziel-Canvas `[w, h]` (Default `1080x1920`); ungerade Werte werden abgerundet |
| `fps` | Ausgabe-FPS (Default 30) |
| `background` | Farbe für Flächen ohne Region: `#RRGGBB`, `#RGB`, `[r,g,b]` oder Name |
| `transition` | Übergang in Sekunden zwischen Clips (Default `0` = harter Schnitt) |
| `expect` | Randbedingungen dieser Spec, siehe unten |
| `clips[]` | Segmente in Reihenfolge; werden verkettet |

### `clip`

| Feld | Bedeutung |
| --- | --- |
| `source` | Videopfad, **relativ zur Spec-Datei** |
| `start` / `end` | Sekunden; ohne `end` bis zum Ende der Quelle |
| `regions[]` | Ausschnitte **derselben** Quelle, auf die Fläche gelegt |
| `overlays[]` | Bilder, zeitlich begrenzt |

### `region`

| Feld | Bedeutung |
| --- | --- |
| `box` | `[x, y, w, h]` in **Quell**pixeln |
| `size` | Zielgröße `[w, h]` (Default: Box-Größe) |
| `position` | `[x, y]` auf dem Canvas oder `"center"` (Default `[0, 0]`) |
| `fit` | `cover` (Default, füllt und beschneidet), `contain` (passt ein, Balken), `stretch` (verzerrt) |
| `start` / `duration` | optional: Region erst später einblenden |

### `overlay`

| Feld | Bedeutung |
| --- | --- |
| `image` | Bildpfad (PNG mit Alpha empfohlen), relativ zur Spec |
| `position` | `[x, y]` oder `"center"` |
| `size` | optionale Zielgröße |
| `start` / `duration` | Sichtbarkeit (ohne `duration`: ab `start` bis Clipende) |
| `opacity` | `0..1` (Default 1) |

## `expect` - was die Spec verlangt

| Schlüssel | Werte | Bedeutung |
| --- | --- | --- |
| `overlap` | `allow` (Default) / `forbid` | dürfen sich Zielregionen überlappen? |
| `fill` | `any` (Default) / `exact` | muss das Canvas **vollständig** bedeckt sein? (Union; Überlappung zählt einmal) |
| `ratio` | `off` (Default) / `warn` / `error` | Quell-Box wird **1:1** abgebildet? Meldet den Verlust: `cover` → Beschnitt, `contain` → Balken, `stretch` → Verzerrung (in %) |

Fehlt `expect`, gelten nur die harten Invarianten: Region außerhalb des Canvas
oder Quell-Box außerhalb des Videos = Fehler.

Unabhängig von `expect` warnt `validate`, wenn die Regionen das Canvas **nicht**
vollständig bedecken (`canvas.uncovered`) und nennt Prozent + offene Pixel.
Ebenso unabhängig: `fit: stretch` mit abweichendem Seitenverhältnis warnt
(`region.stretch`). Das ist die einzige Stelle, an der wirklich verzerrt wird -
`cover` und `contain` verzerren nie.

**Die drei Zusicherungen sind getrennt:**

- `fill: exact` → Canvas ist vollständig bedeckt (keine Ränder)
- `ratio: exact` → die Quell-Box wird vollständig abgebildet (kein Beschnitt, keine Balken)
- `stretch` → nie, außer die Spec will es; dann warnt `region.stretch`

Für die Action-Box (9:16, volle Quellhöhe) gilt beides: `cover` füllt das Canvas
**und** `ratio` ist deckungsgleich → kein Verlust.

## Codes

`size.invalid`, `size.odd`, `fps.invalid`, `background.invalid`, `clips.empty`,
`clip.source.*`, `clip.time.*`, `region.box.*`, `region.size.*`,
`region.position.*`, `region.fit.*`, `region.outside_canvas`, `region.overlap`,
`region.ratio`, `canvas.gap`, `overlay.*`, `transition.*`, `audio.partial`,
`expect.invalid`.

## Grenzen (bewusst)

- Nur Schnitt, Regionen/Layout, Concat, optionale Übergänge, Bild-Overlays,
  Standbilder (`frames`).
- **Kein** Noise/Effekte, kein Audio-Mixing. Untertitel sind ein separater
  ffmpeg-Pass (`subtitles burn`) auf das fertige Video.
- Ton wird nur übernommen, wenn **alle** Clips eine Tonspur haben; sonst läuft
  das Video stumm (Warnung `audio.partial`).
- Unbekannte Spec-Felder werden ignoriert - `name` pro Region und ein
  `boxes`-Block (OCR-Anker) dürfen im selben File stehen.
