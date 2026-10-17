# subtitles

> **Aufruf:** `~/.openclaw/workspace-brainrothustler/bin/cli <modul>.cli <args>`
> (Workspace-Wrapper, siehe `TOOLS.md`) — aus jedem cwd, venv wird automatisch aktiviert.

Untertitel bleiben ein **eigenes Artefakt** (SRT/VTT) — dieses Modul versteckt sie
nie im Video. Zwei unabhängige Schritte:

- **Schneiden** (`parse` / `window` / `write_srt`): aus einem Transcript (VTT oder
  SRT) ein clip-relatives Fenster herausschneiden — **ohne Video**.
- **Einbrennen** (`burn`): eine Untertiteldatei auf ein Video rendern (ffmpeg +
  libass).

So kannst du einbrennen **oder** weich als eigene Spur lassen **oder** den Text nur
für Titel/Beschreibung/Hashtags lesen — ohne das Video neu zu erzeugen.

## CLI

```
~/.openclaw/workspace-brainrothustler/bin/cli subtitles.cli info --in transcript.vtt
~/.openclaw/workspace-brainrothustler/bin/cli subtitles.cli numbers --in transcript.vtt --min 6 --max 10
~/.openclaw/workspace-brainrothustler/bin/cli subtitles.cli words  --in transcript.vtt --at 326 --window 3
~/.openclaw/workspace-brainrothustler/bin/cli subtitles.cli snap   --in transcript.vtt --at 326 --mode sentence --direction before
~/.openclaw/workspace-brainrothustler/bin/cli subtitles.cli cut  --in transcript.vtt --start 1200 --end 1220 --snap sentence --text --out clip.srt
~/.openclaw/workspace-brainrothustler/bin/cli subtitles.cli burn --in clip.mp4 --subs clip.srt --out out.mp4 \
    --font-size 64 --margin-v 220 --outline 3
```

- `numbers`: findet **score-artige Zahlen** im Transkript (Ziffern `8.25` **und**
  ausgesprochen `nine point five`) — die natürlichen **Schnitt-Anker**, weil die
  Bewertungen angesagt werden. `--min/--max` filtern (z. B. 6…10).
- `words`: **nur** die Wörter um `--at` (±`--window`, max. `--limit`) — für einen
  unklaren Moment; nie das ganze Transkript ausgeben. Nutzt die Inline-Tags
  `<00:00:01.234>` aus YouTube-Auto-Captions; ohne Tags sind die Zeiten
  Cue-genau und mit `approx: true` markiert.
- `snap`: eine **Wort-/Satzgrenze** zu `--at` (`before`/`after`/`nearest`) —
  ein kleines Objekt statt Kontext.
- `cut`: `--snap sentence|word` zieht Start/Ende **nach außen** auf die nächste
  Grenze; `--text` gibt den kurzen Clip-Text mit (für Titel). `--no-offset`
  behält absolute Timestamps, `--no-clean` schaltet das Entdoppeln ab.
- `burn`: `--style "…"` überschreibt roh; sonst aus `--font/--font-size/--outline/
  --alignment/--margin-v` gebaut. Audio wird kopiert (Fallback AAC).

Ausgabe ist immer JSON.

## Python-API

```python
from subtitles import subs

cues = subs.load("transcript.vtt")            # [{'start','end','text','raw'}]
cues = subs.dedupe(cues)                      # rollende Dopplungen mergen
hits = subs.find_numbers(cues, lo=8)          # score-artige Zahlen (Schnitt-Anker)
words = subs.words(cues)                      # Wortstarts aus Inline-Tags
near = subs.window_words(words, 326, seconds=3)   # kleines Fenster
bound = subs.snap(326, words, mode="sentence", direction="before")
clip = subs.window(cues, 1200, 1220)          # clip-relativ
subs.write_srt(clip, "clip.srt")
style = subs.build_style(font_size=64, margin_v=220, outline=3)
subs.burn("clip.mp4", "clip.srt", "out.mp4", force_style=style)
```

Fehler werfen `subtitles.SubtitleError` (schlechte Datei oder ffmpeg-Fehler).

## Token-sparsam (für den Agenten)

Das VTT bleibt **in der Datei** — der Agent liest es nie komplett. Er fragt nur:

- `words --at <t> --window 3` → ~10–30 Wörter,
- `snap --at <t>` → ein Boundary-Objekt,
- `cut --snap sentence --text` → angepasste Zeiten + kurzer Text.

So kostet eine Schnittentscheidung ~50–300 Tokens statt ~25k für ein 2-h-Transcript.

## Hinweise

- `cut` akzeptiert VTT **und** SRT; Tags (`<i>`, `<00:00:00.000>`) werden entfernt.
- Auto-Caption-Timestamps sind ±1–2 s ungenau — bei einem Vorlauf (Lead) egal.
- Braucht `ffmpeg` mit libass (über `imageio-ffmpeg` vorhanden).
