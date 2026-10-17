# yt_clips

> **Aufruf:** `~/.openclaw/workspace-brainrothustler/bin/cli <modul>.cli <args>`
> (Workspace-Wrapper, siehe `TOOLS.md`) — aus jedem cwd, venv wird automatisch aktiviert.

State + Ablauf für die **YT-Clip**-Art: ein langes YouTube-Video (Sport) wird in
mehrere vertikale Clips zerlegt.

**Hybrid-Format:** Boxen einmal **pro Video** erkennen (4 Frames → Vision), pro
**Clip** nur auswählen, welche Boxen gelten (`--only` / `--drop`), und nur im
Fallback pro Clip neu erkennen. Der Zustand liegt in `data/brainrot.db`
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
~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli format-set --source 3 --regions fmt.json
~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli format-set --clip 5   --regions fmt.json   # per-Clip (Fallback)
~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli format-get  --source 3
~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli candidates-add --source 3 --json cands.json
~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli candidates-list --source 3 [--status Candidate]
~/.openclaw/workspace-brainrothustler/bin/cli yt_clips.cli clip --clip 5 --out out.mp4 --size 1080x1920 [--only a,b | --drop a,b] [--used]
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
 "boxes": {"scoreboard": [0, 0, 1920, 120], "action": [440, 160, 1040, 620]},
 "regions": [
   {"name": "scoreboard", "box": [0, 0, 1920, 120],    "size": [1080, 68],  "position": [0, 0]},
   {"name": "action",     "box": [440, 160, 1040, 620], "size": [1080, 800], "fit": "cover", "position": [0, 80]}
 ]}
```

`clip` nutzt das Clip-Format, sonst das der Quelle. `--only/--drop` filtern nach
`name` (unbenannte Regionen bleiben immer). `crop-frame` liefert `offset` mit —
darauf die Unterboxen aus Stufe 2 zurückrechnen.

## Candidaten

```json
[{"start": 1200.0, "end": 1235.0, "reason": "Tor"}]
```

`highlights` erzeugt sie automatisch aus **Kapiteln** (`chapters_json`) und
**Audio-Peaks** (Lautheit) — ohne API-Kosten.

## Untertitel

`download --subs-lang en` holt das Transcript mit (`subs_path` am Source, sichtbar
in `next`/`list`). Fenster + Einbrennen macht das Modul `subtitles`.
