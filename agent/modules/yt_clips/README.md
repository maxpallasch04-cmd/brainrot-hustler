# yt_clips

> **Aufruf:** `~/.openclaw/workspace-brainrothustler/bin/channel <id> <modul>.cli <args>`
> (Workspace-Wrapper, siehe `TOOLS.md`) — aus jedem cwd, venv wird automatisch aktiviert.

State + Ablauf für die **YT-Clip**-Art: ein langes YouTube-Video (Sport) wird in
mehrere vertikale Clips zerlegt.

**Dieses Modul rendert nicht und kennt kein Layout.** Die Format-Erkennung
(4 Frames → Vision) endet in einer **Spec für `editor`**; der Agent schreibt
es und ruft `editor.cli validate/render`. Der Zustand hier ist nur: Quellen,
Kandidaten, Status, Analyse.

- `yt_source.status`: `Downloaded` → Kandidaten suchen; `Exhausted` → nichts
  mehr zu clippen.
- `yt_clip.status`: `Candidate` → `Used` / `Skipped`.

Der Zustand liegt in `memory/brainrot.db` (`BRAINROT_DB`), Tabellen `yt_source` +
`yt_clip` (geteilt mit `longterm_memory`). Jede Zeile gehört einem Kanal
(`yt_source.channel_id`); ein `Store` ohne `channel=` startet nicht.

## Rezept als Queue-Schlüssel

Jedes Video trägt ein `recipe`-Feld (gesetzt beim `download`, nachtragbar per
`recipe-set`). `next` **verlangt** ein Rezept und sieht nur dessen Quellen:

```
next --recipe ytsls-besttrick
```

Damit mischt sich kein altes SLS-Material in eine andere Art, und du kannst
parallel an zwei Rezepten arbeiten. `download` ohne `--recipe` wird abgelehnt,
damit kein Video ohne Marker in der DB landet. `list --recipe` filtert die
Übersicht; `list` ohne Filter zeigt alle.

## CLI

```
~/.openclaw/workspace-brainrothustler/bin/channel <id> yt_clips.cli next --recipe <name>             # clip | find | download, pro Rezept
~/.openclaw/workspace-brainrothustler/bin/channel <id> yt_clips.cli download --url <url> --out-dir clips --recipe <name> [--subs-lang en]
~/.openclaw/workspace-brainrothustler/bin/channel <id> yt_clips.cli recipe-set --source <id> --recipe <name>   # Marker nachtragen
~/.openclaw/workspace-brainrothustler/bin/channel <id> yt_clips.cli highlights --source 3 --top 10 --add   # Kapitel + Audio-Peaks
~/.openclaw/workspace-brainrothustler/bin/channel <id> yt_clips.cli crop-frame --in memory/<channel>/screenshots/<bild>.png --box <box> --out memory/<channel>/screenshots/sb.png --scale 2
~/.openclaw/workspace-brainrothustler/bin/channel <id> yt_clips.cli boxes-set --source 3 --json boxes.json   # Messung, pro Video
~/.openclaw/workspace-brainrothustler/bin/channel <id> yt_clips.cli boxes-get --source 3
~/.openclaw/workspace-brainrothustler/bin/channel <id> yt_clips.cli motion --clip 5
~/.openclaw/workspace-brainrothustler/bin/channel <id> yt_clips.cli motion --source 3 --from 300 --to 360
~/.openclaw/workspace-brainrothustler/bin/channel <id> yt_clips.cli ocr --clip 5 --box 1200,80,180,90 --step 1
~/.openclaw/workspace-brainrothustler/bin/channel <id> yt_clips.cli ocr --source 3 --box 1200,80,180,90 --from 300 --to 340 --step 1
~/.openclaw/workspace-brainrothustler/bin/channel <id> yt_clips.cli candidates-add --source 3 --json cands.json
~/.openclaw/workspace-brainrothustler/bin/channel <id> yt_clips.cli candidates-list --source 3 [--status Candidate]
~/.openclaw/workspace-brainrothustler/bin/channel <id> yt_clips.cli used --clip 5 [--video-id 12]    # nach dem Render
~/.openclaw/workspace-brainrothustler/bin/channel <id> yt_clips.cli skip --clip 5
~/.openclaw/workspace-brainrothustler/bin/channel <id> yt_clips.cli list [--recipe <name>]
```

Rendern läuft über `editor`:

```
~/.openclaw/workspace-brainrothustler/bin/channel <id> editor.cli validate --spec memory/<channel>/specs/<name>.json
~/.openclaw/workspace-brainrothustler/bin/channel <id> editor.cli render   --spec memory/<channel>/specs/<name>.json --out memory/<channel>/videos/<name>.mp4
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
(enthält `yt-dlp-ejs`) plus eine Runtime. **Node wird automatisch erkannt**, wenn
es im PATH liegt (`net_opts()` setzt dann `js_runtimes=node`);
`YTDLP_JS_RUNTIMES` ist nur noch ein Override. Fehlt die Runtime, kommt
`n challenge solving failed` → Formate fehlen → `Requested format is not
available`. Dazu der PO-Token-Provider (`bgutil-ytdlp-pot-provider`).

Auf der VPS bewährt: `YTDLP_EXTRACTOR_ARGS=youtube:player_client=web_safari`
(`mweb`/`tv` enden dort in `The page needs to be reloaded`).

## Boxen (Messung, pro Video)

Die Unterboxen aus der Vision (`score`, `name`, `list` …) liegen **einmal pro
Quelle** im Store — kanonisch, in Quellkoordinaten:

```
~/.openclaw/workspace-brainrothustler/bin/channel <id> yt_clips.cli boxes-set --source 3 --json boxes.json
~/.openclaw/workspace-brainrothustler/bin/channel <id> yt_clips.cli boxes-get --source 3
```

`next`/`list` geben die Boxen als `boxes` mit aus. Die **Spec kopiert**, was sie
braucht (`boxes.score` als OCR-Anker). `ocr` liest **nicht** aus der DB — es
bekommt die Box als `--box` vom Aufrufer.

## Format (pro Video)

Spec-Ausschnitt für `editor`: `regions` **benannt** (Label für Menschen) und
optional die rohen Boxen. `boxes` wird vom Editor ignoriert — es ist der
OCR-Anker, den `yt_clips ocr --box` benutzt:

```json
{"size": "1080x1920", "background": "#000000",
 "boxes": {"score": [120, 30, 220, 80], "scoreboard": [80, 10, 340, 900],
           "action": [440, 0, 607, 1080]},
 "regions": [
   {"name": "action", "box": [440, 0, 607, 1080], "size": [1080, 1920],
    "fit": "cover", "position": "center"},
   {"name": "scoreboard", "box": [80, 10, 340, 900], "size": [320, 848],
    "fit": "contain", "position": [740, 40]}
 ]}
```

**Action:** eine **Box pro Clip**, die den Akteur über alle relevanten Kameras
enthält (meist die Mitte). Die Box ist **9:16 in voller Quellhöhe** (Breite =
Höhe × 9/16), `fit: cover`, `position: center` → füllt 1080x1920, **keine
schwarzen Ränder, kein zusätzlicher Beschnitt**. Eine breitere Box wird von
`cover` seitlich beschnitten; `contain` erzeugt Balken.

**Scoreboard:** die vertikale Kachel als kleine Region in einer Ecke (`contain`,
≈ 25–35 % der Ausgabebreite), **kein Band oben, keine volle Breite**. Die
Score-Box wird damit nicht als Band gerendert. `boxes` hält die Unterboxen in
**Quellkoordinaten** — `boxes.score` ist der Zahlenkasten und die **OCR-Box**.
Die Koordinaten sind
pro Video **fix**; nur der Inhalt wechselt (leer/Score). Deshalb kein per-Clip-
Re-Detect — pro Clip nur OCR auf `boxes.score` über die Zeit.

Die Auswahl, welche Regionen ein Clip zeigt, entsteht beim **Schreiben der
Spec**: einfach die nicht gewünschten Regionen weglassen. `crop-frame` liefert
`offset` mit — darauf die Unterboxen aus Stufe 2 zurückrechnen.

`editor.cli validate` gibt **`errors`/`warnings`** zurück. Sie melden mit Zahlen,
wenn die Action-Box **nicht 9:16** ist (cover beschneidet sie), `contain`
Balken hinterlässt, das Scoreboard als Band liegt (> 50 % Breite) oder das
Canvas nicht bedeckt ist (`canvas.uncovered`). Eine 9:16-Box mit `cover` ist
warnungsfrei. Weitere Codes: Region über den Canvas hinaus, Region überlappt,
Box außerhalb der Quelle, `stretch` verzerrt. Fehler blocken den Render,
Warnungen nicht. Die
Action-Region muss den Akteur über den ganzen Clip zeigen; an jeder Seite
**≥ 10 % Rand** — das prüft das Modell an 3–5 Frames (die CLI sieht keine
Bildinhalte).

## OCR (Score)

`ocr` liest die **feste `boxes.score`** (keine per-Clip-Erkennung) und gibt Werte
**0.0–10.0** aus. Leere Frames werden ignoriert — kein Vision-Modell.

```
~/.openclaw/workspace-brainrothustler/bin/channel <id> yt_clips.cli ocr --clip 5 --box 1200,80,180,90 --step 1
~/.openclaw/workspace-brainrothustler/bin/channel <id> yt_clips.cli ocr --source 3 --box 1200,80,180,90 --from 300 --to 340 --step 1
```

- `--box` ist die Score-Box in **Quellkoordinaten** (`boxes.score` aus der Spec).
- `--clip` nutzt das Clip-Fenster; `--source` braucht `--from/--to` oder `--at`.
- Ausgabe: `first`, `first_stable` (erster Treffer mit **≥ 2** aufeinanderfolgenden
  Werten), `runs` (`start/end/value`), `checked`, `empty`. `--all` hängt alle
  Einzel-Hits an.
- Engine: **Tesseract** (Binary; `TESSERACT_CMD` oder PATH). `--engine rapidocr`
  ist optionaler Fallback, wenn installiert. `--pad/--scale` steuern den Crop.
- `first_stable` ist der **End-Anker** für einen Score-Clip, nicht die Ansage.

## Motion (Start-Anker)

`motion` misst Frame-Differenzen lokal (MoviePy + NumPy, kein Vision-Modell):
Frames werden mit `--fps` (Default 4) gelesen, auf `--width` (Default 160)
verkleinert und als Graustufen-Differenz verglichen. Ausgabe:
`first_motion`, `last_motion`, `moving_ratio`, `segments` (zusammenhängende
Bewegungsphasen).

```
~/.openclaw/workspace-brainrothustler/bin/channel <id> yt_clips.cli motion --source 3 --from 300 --to 360
~/.openclaw/workspace-brainrothustler/bin/channel <id> yt_clips.cli motion --clip 5
```

Der **Start-Anker ist `first_motion`** (minus ~2 s Anlauf), nicht die Ansage und
nicht ein geschätzter `pre_roll`. `--threshold` (0..1, Default adaptiv mit Floor
0.005) macht die Messung strenger/lockerer.

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

Beide Segmentkanten vorher mit `editor.cli subtitles snap` auf Satz-/Wortgrenzen legen
(Start `before`, Ende `after`) — **nie mitten in einen Kommentatorsatz schneiden**,
auch nicht am Übergang Trick → Score. In der Spec werden die Segmente zu
`clips[]` (zwei Einträge, ggf. mit `transition`).

`highlights` erzeugt sie automatisch aus **Kapiteln** (`chapters_json`) und
**Audio-Peaks** (Lautheit) — ohne API-Kosten.

## Untertitel

`download --subs-lang en` holt das Transcript mit (`subs_path` am Source, sichtbar
in `next`/`list`). Fenster + Einbrennen macht das Modul `subtitles`.
