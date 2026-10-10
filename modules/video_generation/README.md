# video_generation

Editing-Toolkit: schneiden, auf eine 9:16-Fläche einpassen, Bilder an `(x, y, t)`
überlagern, Audio mischen und verketten. Für jede Videoart nutzen (selbstgeneriert,
Clips).

Ausgabe ist standardmäßig `1080x1920`; die Vorgabe verlangt mindestens **720p**
(Höhe ≥ 1280). `render_recipe` meldet eine `warning`, wenn die Höhe < 1280 ist.

## Python-API

```python
from video_generation import edit

clip = edit.load("raw.mp4")
clip = edit.cut(clip, 12, 18)                      # Sekunden
clip = edit.on_background(clip, (1080, 1920), "#101010")
clip = edit.overlay(clip, "logo.png", x=40, y=80, start=0.5, duration=3, size=(160, 160))
clip = edit.add_audio(clip, "sfx.mp3", start=1.0, volume=0.8)
clip = edit.noise(clip, amount=0.06, mode="grain")  # Filmkorn / VHS
edit.render(clip, "out.mp4", fps=30)
clip.close()
```

Funktionen: `cut`, `contain`, `cover`, `on_background`, `overlay`, `noise`,
`add_audio`, `concat`, `render`, `probe`, `render_recipe`. `background` ist `None`
(schwarz), eine Farbe (`#111` / `black` / `[r,g,b]`), ein Bild oder ein Video
(geloopt). `x`/`y` akzeptieren Pixel oder `"center"`.

## Rezept (ein JSON → ein Video)

`render_recipe` baut ein Video aus einem dict; die CLI `render` akzeptiert dieselbe
Form (Datei oder `-` für stdin). `clips[]` werden in Reihenfolge verkettet.

```json
{
  "size": [1080, 1920],
  "fps": 30,
  "background": "#000000",
  "noise": {"amount": 0.08, "mode": "vhs"},
  "out": "out.mp4",
  "audio": [{"source": "music.mp3", "start": 0, "volume": 0.3}],
  "clips": [
    {
      "source": "twitch.mp4",
      "start": 12.0,
      "end": 18.0,
      "background": "blur.png",
      "margin": 0,
      "overlays": [
        {"image": "follow.png", "x": "center", "y": 1600, "start": 4.0,
         "duration": 2.0, "size": [400, 100], "opacity": 1.0}
      ],
      "audio": [{"source": "pop.mp3", "start": 4.0, "volume": 0.8}]
    }
  ]
}
```

- `overlays[]`: ab `start` für `duration` gezeigt (Standard: Rest des Clips).
- `noise`: `true`, eine Zahl (Stärke) oder `{amount, mode, monochrome, seed}` —
  zufälliges Korn pro Frame; `mode` ist `grain` oder `vhs`. Gilt auf Top-Level
  und/oder pro Clip.
- `audio[]`: pro Clip; die Top-Level-`audio[]` wird über das ganze Ergebnis
  gemischt.
- `out` kann mit dem CLI-Flag `--out` überschrieben werden.

## CLI

```
python3 -m video_generation.cli probe      --in raw.mp4
python3 -m video_generation.cli cut        --in raw.mp4 --start 12 --end 18 --out cut.mp4
python3 -m video_generation.cli background --in cut.mp4 --out bg.mp4 --size 1080x1920 --bg "#101010"
python3 -m video_generation.cli overlay    --in bg.mp4  --out ov.mp4 --image logo.png --x 40 --y 80 --start 0.5 --duration 3
python3 -m video_generation.cli noise      --in ov.mp4  --out gr.mp4 --amount 0.08 --mode vhs
python3 -m video_generation.cli audio      --in ov.mp4  --out au.mp4 --audio sfx.mp3 --start 1.0 --volume 0.8
python3 -m video_generation.cli concat     a.mp4 b.mp4 --out merged.mp4
python3 -m video_generation.cli render     --recipe recipe.json
```

Alle Befehle geben JSON aus.
