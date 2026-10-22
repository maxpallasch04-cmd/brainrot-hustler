# AGENTS.md - BrainrotHustler

Du Planst Uploads und Produzierst Kurzform Videos für mehrere Kanäle.

## Aufgabe

Ein Aufruf entscheidet über deine Aufgabe:

```
~/.openclaw/workspace-brainrothustler/bin/cli longterm_memory.cli task
```

`action` sagt, was zu tun ist, `channel` sagt, für wen:

| `action` | Bedeutung | was du tust |
| -------- | --------- | ----------- |
| `upload` | `generated` und Uploadzeit vorbei | für `channel` melden, dass hochgeladen werden soll (`video`; alle Fälle in `videos`) |
| `pipeline` | ein `planned`-Eintrag ist fällig (Upload in < `lead_h`) | **Pipeline-Skill** für `channel` mit `video` (Rohzeile: `entry`) ausführen |
| `plan` | `open < target` | mit `add-plan` für `channel` neue Einträge anlegen, bis `open` = `target` |
| `idle` | nichts fällig | nichts tun |

- `video` sagt, um welches Video es geht: `id`, `label`, `title`, `idea`,
  `recipe`, `file`, `plan_at_local`, `status`. Bei `pipeline` der fällige
  Eintrag, bei `upload` das dringendste der Liste, bei `plan`/`idle` fehlt es.
- `entry` (bei `pipeline`) ist der komplette DB-Eintrag, `videos` (bei `upload`)
  die Liste der fälligen Videos.
- Nach dem das Hochladen vom Nutzer bestätigt wurde: `bin/channel <channel> longterm_memory.cli upload <id>`.

## Kanal

Alles Kanalspezifische steht **nicht hier**, sondern im Profil:

```
~/.openclaw/workspace-brainrothustler/bin/cli longterm_memory.cli channel-get <id>
```

Die `<id>` kommt aus `task` → `channel`; `channel-list` zeigt alle Kanäle.

Die Kanalinformationen sind Essenziell für die Planung neuer Videos:

- `niche` : Nische in einem Satz
- `art` : Standard-Videoart
- `recipes` : aktive Rezepte (JSON-Liste) - andere `add-plan`s werden abgelehnt
- `open_target` / `lead_h` : Zahl der offenen Planeinträge / Vorlaufzeit der Generierung in Stunden
- `quiet_start` / `quiet_end` : Ruhezeiten in `tz` - `add-plan` lehnt Zeiten darin ab
- `format` : Zielformat (z. B. `9:16,1280`)
- `recipients` : wer Upload-Meldungen bekommt

## Workspace

Im Workspace-Root liegen folgende Elemente:

- **`recipes/`** : Vorgaben, die das **wie** der Videoerstellung definieren.
- **`memory/`** :
  - `brainrot.db` - geteilte Datenbank: Kanäle, Plan, Video-Gedächtnis (Spalte `channel_id`)
  - `<channel>/` - alles, was der Agent für diesen Kanal produziert:
    - `videos/` - fertige Renders
    - `clips/` - Rohmaterial / Downloads (`.mp4`, `.json`, `.vtt`)
    - `screenshots/` - Frames, Crops, Standbilder
    - `specs/` - Editor-Specs
- **`modules/`** - nur Code. Dort keine Videos, Clips oder Bilder ablegen.
- `AGENTS.md`, `skills/`, `bin/`

Pfade: in einer Editor-Spec löst `editor` `"source"` **relativ zur Spec-Datei**
auf, `--out` relativ zum cwd, alle anderen relativen Pfade relativ zum Workspace-Root.

## Werkzeuge

### Wrapper

Module sind nur über einen der beiden Wrapper nutzbar.

```
~/.openclaw/workspace-brainrothustler/bin/cli     <modul>.cli [args]
~/.openclaw/workspace-brainrothustler/bin/channel <id> <modul>.cli [args]
```

- **`bin/cli`** - kanal-frei: `editor`, `longterm_memory.cli task` (entscheidet
  über alle Kanäle) und Kanal-Administration (`longterm_memory.cli channel-list |
  channel-get <id> | channel-set <id>`).
- **`bin/channel <id>`** - erster Parameter ist **immer** die Kanal-ID; setzt
  `BRAINROT_CHANNEL` und reicht an `cli` weiter. `yt_clips` und `hosting` laufen
  nur so.

- Relative Pfade beziehen sich auf den Workspace.
- Links immer in Anführungszeichen übergeben (`--url "https://…"`)
- stdout = JSON, Fortschritt/Fehler = stderr.

### Module

- **editor** - Schnitt, Regionen/Layout, Bild-Overlays, Übergänge, Untertitel,
  Standbilder. **Kanal-frei.** → `modules/editor/README.md`
- **yt_clips** - Quellen, Kandidaten, Status, OCR/Motion/Highlights. **Kanalspezifisch**
  (Quellen + Kandidaten). → `modules/yt_clips/README.md`
- **hosting** - Upload zu Cloudflare R2, öffentliche URL. **Kanalspezifisch.**
  `R2_KEEP=1` (Default): nur das neueste Video bleibt - der Link aus dem Lauf
  davor ist nach dem nächsten Upload tot. → `modules/hosting/README.md`
- **longterm_memory** - Contentplan **und** Video-Gedächtnis (SQLite) plus
  Kanalprofile: `planned` → `generated` → `uploaded`.
  → `modules/longterm_memory/README.md`

## Konventionen

- Jedes CLI gibt **JSON** aus - parsen.
- **Rezept** = inhaltliche Vorgabe (`recipes/<name>.md`).
- **Spec** = JSON für den Editor (ein Clip).

## Links

- Genaue CLI Doku → `modules/<modulname>/README.md`
- Kanal anlegen/ändern → `skills/channel-setup`
- Ablauf im Detail → `skills/pipeline`
- Heartbeat-Checks → `HEARTBEAT.md`
- Inhaltswissen → `recipes/<name>.md`
