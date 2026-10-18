# 2026-10-18 — CLI-Erkenntnisse: wie man ein korrektes Video rendert

Gesammelt aus dem SLS-Best-Trick-Lauf (Braden Hoban, 9.5). Das ist die Wahrheit
über die Werkzeuge, nicht über das Rezept.

## 1. Render-Reihenfolge (die eigentliche Ursache von 4 Fehlschlägen)

Falsch: `layout` auf das ganze Fenster → `concat` → Audio dazu.
Richtig, und zwar in dieser Reihenfolge:

1. `video_generation.cli cut` am **Original** (behält Ton) — ein Segment pro Fenster.
2. `layout` **pro Segment** mit `--regions` (Action `cover` auf 1080x1920).
3. `concat` der fertigen Segmente → Ton bleibt intakt.
4. `overlay` / `subtitles.cli burn` **danach**.

Andersherum zerlegt der AAC-Mux den File: `BrokenPipeError` / „MoviePy error …
writing out.mp4", Ergebnis truncated („moov atom not found").
Jeder Schritt einzeln = bei einem Fehler ist nur ein Segment kaputt, nicht alles.

## 2. Bild füllen statt einpassen

- `background` = **contain** → Briefmarke im Mittelband mit schwarzen Balken.
  Genau das ist mir passiert.
- Ganze Fläche füllen: `layout --regions` mit
  `{"box":[0,0,1280,720],"size":[1080,1920],"fit":"cover"}`.
- `cover` auf eine **schmale** Box (z.B. Scoreboard 222x520) schneidet nicht ab,
  es **verzerrt/erfindet Pixel** → unlesbar. Für Kacheln `contain`, für Action
  `cover`. `stretch` nie.
- Regions **ohne `size`** rendern in Quellgröße mitten auf die Fläche.
  `layout` warnt dabei nicht. Immer `size` + `position` setzen, `warnings` lesen.

## 3. Scoreboard finden — Frame ansehen, nicht rechnen

- Eine aus einem falsch skalierten Screenshot abgeleitete Box (`[258,110,106,18]`)
  zeigte auf nichts. Richtig: Frame ziehen → ansehen → Box ablesen →
  `crop-frame --box … --scale 2` gegenprüfen.
- Zu schmale Box = abgeschnittene Zahl (9.5 halb weg). Board ist `[78,88,300,520]`.
- Kachel als **Standbild** einfrieren (`frames --at`) und per `overlay` legen:
  `crop --box 78,88,300,520 --size 440x763 --fit contain`, dann `overlay --size 440x764`,
  Position ~40/60 px oben links, ~40 % Breite. Nicht volle Breite.
- Overlays liegen **über** der Action; Action muss den ganzen Hintergrund decken.

## 4. Dateien prüfen, bevor ich sie als fertig melde

- `probe` meldet Länge/Größe **auch bei kaputten Dateien** — kein Beleg.
- Echter Test: `frames --at <mehrere>`; wirft der Reader
  „0 bytes read at frame N", ist der File truncated (so war `a0.mp4`).
- QC immer im **Renderergebnis**, nicht im Zwischenschritt. Ich habe Kachel und
  Layout je einzeln geprüft und trotzdem einen Clip ausgeliefert, in dem der
  Skater als Briefmarke im Mittelband stand.

## 5. Pfade und Flags

- Der Wrapper läuft **in `modules/`**: `--out clip.srt` landet in `modules/clip.srt`,
  nicht im Workspace. `burn` mit einem Workspace-Pfad bricht ab („not a file").
  Absolute Pfade oder `modules/…` verwenden.
- `--progress` existiert nur bei `video_generation layout|render`. Bei `overlay`,
  `crop`, `concat`, `background`, `subtitles burn` ist es ein unbekanntes Flag →
  Exit 2, kein Fallback. Argument-Fehler immer von Render-Fehlern trennen.
- `longterm_memory add-video --len-s` will einen **int** (`11`, nicht `10.8`).

## 6. Untertitel: Datei erst verstehen

- `cut --snap sentence` erzeugte aus dieser VTT 59 Cues mit 34-ms-Fragmenten
  („why this trick is so", dreifach überlappend). `burn` lief fehlerfrei durch,
  im Bild war **nichts**.
- Vor dem Brennen: `info` (Cue-Anzahl, `last_end`) + erste ~20 Zeilen lesen.
  Faustregel: Cues > Videolänge in Sekunden × 3 = kaputt, erst reparieren.
- Zweimal brennen ohne Sichtprüfung ist verbrannte Zeit. Prüfen, dann rendern.

## 7. Umgebung (VPS)

- Ohne Swap: 1080x1920 mit Audio zuverlässig OOM/SIGKILL. Mit 4 GB Swap läuft
  derselbe Render durch. Swap ist jetzt gesetzt.
- `ffmpeg`, `ls`, `df`, Chains (`&&`, `;`) direkt werden von der Exec-Policy
  verweigert — nur `bin/cli`. Nicht dagegen ankämpfen, Lösung im Wrapper suchen.
- Lange Renders: `yieldMs`/`process poll` nutzen, nicht blind warten.

## 8. Kommunikation

- 45 min stilles Rendern war der schlimmste Fehler des Laufs. Bei mehrstufiger
  Arbeit: Zwischenmeldung nach dem ersten erfolgreichen Schritt, dann bei jedem
  Wechsel der Ursache — nicht erst am Ende.
- Fertig ist ein Video erst mit Titel, Beschreibung, gerenderter `.mp4` **und**
  sichtgeprüften QC-Frames.
