# yt_clips

> **Aufruf:** `~/.openclaw/workspace-brainrothustler/bin/cli <modul>.cli <args>`
> (Workspace-Wrapper, siehe `TOOLS.md`) — aus jedem cwd, venv wird automatisch aktiviert.

State + Ablauf für die **YT-Clip**-Art: ein langes YouTube-Video (Sport) wird in
mehrere vertikale Clips zerlegt.

**Format pro Video:** Boxen einmal **pro Video** erkennen (4 Frames → Vision).
Die Score-Box (`boxes.score`) ist **statisch** — pro Clip wird sie **nicht** neu
erkannt; pro Clip wird nur ausgewählt, welche Regionen gelten (`--only`/`--drop`).
`format-set --clip` nur bei echten Szenenwechseln (Interview/Studio), nicht fürs
Scoreboard. Der Zustand liegt in `data/brainrot.db`
(`BRAINROT_DB`), Tabellen `yt_source` + `yt_clip` (geteilt mit `longterm_memory`).

- `yt_source.status`: `Downloaded` → kein Format; `Formatted` → Format da;
  `Exhausted` → nichts mehr zu clippen.
- `yt_clip.status`: `Candidate` → `Used` / `Skipped`.

## CLI

```
~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli next                                   # format | clip | find | download
~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli download --url <url> --out-dir clips --recipe <name> [--subs-lang en]
~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli highlights --source 3 --top 10 --add   # Kapitel + Audio-Peaks
~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli crop-frame --in frames/<bild>.png --box <box> --out sb.png --scale 2
~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli ocr --clip 5 --step 1
~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli ocr --source 3 --from 300 --to 340 --step 1
~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli format-set --source 3 --regions fmt.json
~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli format-set --clip 5   --regions fmt.json   # per-Clip (Fallback)
~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli format-get  --source 3
~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli candidates-add --source 3 --json cands.json
~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli candidates-list --source 3 [--status Candidate]
~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli clip --clip 5 --out out.mp4 --size 1080x1920 [--only a,b | --drop a,b] [--progress] [--used]
# clip rendert ein Fenster oder die gespeicherten segments (A/B) und verkettet sie
# --progress: Start/Prozent/Ende nach stderr (stdout bleibt JSON)
~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli list
```

Alle Befehle geben JSON aus. `--db <pfad>` überschreibt die DB (vor das Subkommando).

## Cookies & gesperrte IPs (Bot-Schutz)

YouTube verlangt auf Rechenzentrums-IPs eine angemeldete Session („Sign in to
confirm you're not a bot"). Der Download liest Cookies automatisch aus einer
Netscape-`cookies.txt`:

- `YTDLP_COOKIES_FILE` — Pfad zur Cookie-Datei (hat Vorrang)
- `YTDLP_COOKIES_FROM_BROWSER` — z. B. `firefox:default` (nur Desktop)
- sonst `$BRAINROT_STATE_DIR/cookies.txt`
  (Default `~/.openclaw/state/brainrot/cookies.txt`), wenn vorhanden

Die Datei ist ein Zugang → **außerhalb** Repo/Workspace halten. yt-dlp schreibt sie
beim Lauf zurück (beschreibbar halten). Schlägt der Download am Bot-Check fehl,
wirft `download` einen Hinweis auf genau diese Optionen.

**Cookies ≠ IP.** Ist die IP/ASN selbst gesperrt, hilft der beste Cookie nichts.
Dafür zwei Schalter (beide ohne Code-Änderung nutzbar):

- `YTDLP_PROXY` — nicht gesperrter Ausgang, z. B.
  `socks5://user:pass@host:1080` oder `http://host:8080`. Residential/Mobile
  wirkt am besten — möglichst dieselbe Region wie die Cookie-Session.
- `YTDLP_EXTRACTOR_ARGS` — z. B. `youtube:player_client=tv,web_safari`
  (entspricht yt-dlp `--extractor-args`; manchmal reicht schon das).

Zusätzlich braucht YouTube eine **JS-Challenge-Lösung**: `yt-dlp[default]`
(enthält `yt-dlp-ejs`) plus eine Runtime — `YTDLP_JS_RUNTIMES=node`
(yt-dlp aktiviert von sich aus nur `deno`). Fehlt das, kommt
`n challenge solving failed`. Dazu der PO-Token-Provider
(`bgutil-ytdlp-pot-provider`).

Auf der VPS bewährt: `YTDLP_EXTRACTOR_ARGS=youtube:player_client=web_safari`
(`mweb`/`tv` enden dort in `The page needs to be reloaded`).

## Format (pro Video)

Regions-Liste für `video_generation.layout`, mit **benannten** Regionen (damit pro
Clip an-/abwählbar) und optional den rohen Boxen:

```json
{"size": "1080x1920", "background": "#000000",
 "boxes": {"score": [120, 30, 220, 80], "name": [40, 20, 180, 60],
           "action": [440, 160, 1040, 620]},
 "regions": [
   {"name": "score",  "box": [120, 30, 220, 80],  "size": [1080, 300],  "fit": "cover", "position": [0, 0]},
   {"name": "action", "box": [440, 160, 1040, 620], "size": [1080, 1620], "fit": "cover", "position": [0, 300]}
 ]}
```

Das **ganze Scoreboard** wird nicht gerendert. `boxes` hält die Unterboxen in
**Quellkoordinaten** — `boxes.score` ist der Zahlenkasten: er wird als Band oben
angezeigt (200–400 px hoch) und ist später die **OCR-Box**. Die Koordinaten sind
pro Video **fix**; nur der Inhalt wechselt (leer/Score). Deshalb kein per-Clip-
Re-Detect — pro Clip nur OCR auf `boxes.score` über die Zeit.

`clip` nutzt das Clip-Format, sonst das der Quelle. `--only/--drop` filtern nach
`name` (unbenannte Regionen bleiben immer). `crop-frame` liefert `offset` mit —
darauf die Unterboxen aus Stufe 2 zurückrechnen.

`format-set` und `clip` geben zusätzlich **`warnings`** zurück, wenn das Layout
nicht die volle Fläche füllt (schwarze Balken), eine Region über den Canvas
hinausgeht, `size`/`position` fehlt, `fit: contain`/`stretch` benutzt wird, das
ganze `scoreboard` statt `score` gerendert wird oder die Score-Box zu klein bzw.
abgeschnitten ist. Sie blocken nicht — sie sind der Hinweis, das Format zu
korrigieren (Rezepte verlangen lückenlose Aufteilung und `cover`). Die
Action-Region muss den Akteur über den ganzen Clip zeigen; an jeder Seite
**≥ 10 % Rand** — das prüft das Modell an 3–5 Frames (die CLI sieht keine
Bildinhalte).

## OCR (Score)

`ocr` liest die **feste `boxes.score`** (keine per-Clip-Erkennung) und gibt Werte
**0.0–10.0** aus. Leere Frames werden ignoriert — kein Vision-Modell.

```
~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli ocr --clip 5 --step 1
~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli ocr --source 3 --from 300 --to 340 --step 1
```

- `--clip` nutzt das Clip-Fenster; `--source` braucht `--from/--to` oder `--at`.
- Ausgabe: `first`, `first_stable` (erster Treffer mit **≥ 2** aufeinanderfolgenden
  Werten), `runs` (`start/end/value`), `checked`, `empty`. `--all` hängt alle
  Einzel-Hits an.
- Engine: **Tesseract** (Binary; `TESSERACT_CMD` oder PATH). `--engine rapidocr`
  ist optionaler Fallback, wenn installiert. `--pad/--scale` steuern den Crop.
- `first_stable` ist der **End-Anker** für einen Score-Clip, nicht die Ansage.

## Candidaten

```json
[{"start": 1200.0, "end": 1235.0, "reason": "Tor"}]
```

Alternativ mit **Score-Anker** statt Start/Ende — die CLI rechnet das Fenster:

```json
[{"score": 326.0, "pre_roll": 20, "post_roll": 3, "reason": "Best Trick"}]
```

`score` ist die **Einblendung** des Scores, nicht die Ansage (die kann 30–60 s
später liegen). `pre_roll` muss den Trick/Run enthalten: Best Trick **≥ 10 s**
(besser 15), Lines = Run-Länge. `candidates-add` warnt bei `pre_roll < 8 s`
(„nur Feier") und bei Fenstern < 5 s.

Kommt der Score später, zwei Fenster (**A/B**): Trick + Score werden beim
Rendern hart aneinandergehängt:

```json
[{"segments": [{"start": 305, "end": 316}, {"start": 324, "end": 330}],
  "reason": "Trick + Score"}]
```

Pro Segment überschreiben `only`/`drop` die globale Regionsauswahl (z. B. im
Score-Fenster nur `score` + `action`). Beide Segmentkanten vorher mit
`subtitles.cli snap` auf Satz-/Wortgrenzen legen (Start `before`, Ende `after`) —
**nie mitten in einen Kommentatorsatz schneiden**, auch nicht am Übergang
Trick → Score.

`highlights` erzeugt sie automatisch aus **Kapiteln** (`chapters_json`) und
**Audio-Peaks** (Lautheit) — ohne API-Kosten.

## Untertitel

`download --subs-lang en` holt das Transcript mit (`subs_path` am Source, sichtbar
in `next`/`list`). Fenster + Einbrennen macht das Modul `subtitles`.
