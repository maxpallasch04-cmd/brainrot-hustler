# longterm_memory

> **Aufruf:** `~/.openclaw/workspace-brainrothustler/bin/cli longterm_memory.cli <cmd> <args>`
> (Workspace-Wrapper, siehe `TOOLS.md`) - aus jedem cwd, venv wird automatisch aktiviert.

Der Contentplan **und** das Gedächtnis des Kanals in einer Tabelle: ein Eintrag
pro Video, von der Idee bis zum Upload.

```
planned  --generated-->  generated  --upload-->  uploaded
```

Es gibt keine `contentplan.md` mehr - die DB ist die Warteschlange.
DB-Pfad: `memory/brainrot.db` (überschreibbar mit `BRAINROT_DB`).

| Feld | Bedeutung |
| ---- | --------- |
| `idea` | ein Satz: was ist das Video (aus der Planung) |
| `title` | finaler Titel (erst ab `generated`) |
| `description` | Caption fürs Upload (erst ab `generated`) |
| `art` | `Selbstgeneriert` \| `Twitch-Clip` \| `YT-Clip` |
| `recipe` | Rezept-ID (`recipes/<name>.md`) |
| `file` | Pfad zur fertigen mp4 (`memory/videos/...`), `NULL` bis gerendert |
| `len_s` | Länge in Sekunden, `0` bis gerendert |
| `plan_at` | **geplante** Uploadzeit (Unix) |
| `upload_at` | tatsächliche Uploadzeit (Unix), `NULL` bis hochgeladen |
| `status` | `planned` \| `generated` \| `uploaded` |

## Python-API

```python
from longterm_memory import LongTermMemory, VideoArt

mem = LongTermMemory()
vid = mem.addPlan("Best Trick, Score 9.10", "ytsls-besttrick", plan_at=1793000000)
mem.markGenerated(vid, title="Insane 9.10 Best Trick", description="...",
                  file="memory/videos/besttrick.mp4", len_s=31)
mem.upload(vid)                 # -> uploaded, setzt upload_at (idempotent)
mem.nextDue()                   # nächster fälliger planned-Eintrag (4 h Vorlauf)
mem.task()                      # Heartbeat: {'action': 'upload'|'pipeline'|'plan'|'idle', ...}
mem.openCount()                 # planned + generated
mem.overdue()                   # generated, Uploadzeit vorbei
```

| Methode | Zweck |
| ------- | ----- |
| `addPlan(idea, recipe, plan_at, art=..., theme="")` | Plan-Eintrag anlegen (`planned`) → id |
| `markGenerated(id, *, title, description, file, len_s, art=None, theme=None)` | Render eintragen (`generated`) |
| `upload(id, at=None)` | als `uploaded` markieren, `upload_at` setzen (idempotent) |
| `getVideo(id)` / `listVideos(status=None)` | lesen, nach `plan_at` sortiert |
| `openCount()` | offene Einträge (`planned` + `generated`) |
| `nextDue(now=None, lead_s=14400)` | nächster fälliger `planned`-Eintrag oder `None` |
| `overdue(now=None)` | `generated`, deren Uploadzeit vorbei ist |
| `task(now=None, lead_s=14400, open_target=2)` | eine Heartbeat-Entscheidung: `upload` \| `pipeline` \| `plan` \| `idle` |

## CLI

```
bin/cli longterm_memory.cli task [--open-target 2] [--lead-h 4]
bin/cli longterm_memory.cli add-plan --idea "..." --recipe ytsls-besttrick --plan-at "2026-10-21 18:00"
bin/cli longterm_memory.cli nextdue [--lead-h 4]
bin/cli longterm_memory.cli open-count
bin/cli longterm_memory.cli generated 1 --title "..." --file memory/videos/x.mp4 --len-s 31 [--description "..."]
bin/cli longterm_memory.cli overdue
bin/cli longterm_memory.cli upload 1 [--at "2026-10-21 18:05"]
bin/cli longterm_memory.cli get-video 1
bin/cli longterm_memory.cli list-videos [--status planned|generated|uploaded]
```

`task` ist der Herzstück-Befehl für den Heartbeat - eine Antwort, eine Aktion:

```json
{"action": "pipeline", "open": 2, "target": 2, "also": [], "entry": {"id": 3, "idea": "...", ...}}
```

Priorität: `upload` → `pipeline` → `plan` → `idle`. Zusätzlich Anstehendes steht in
`also`; `entry` und `videos` sind immer dabei, wenn sie existieren.

Zeiten: Unix-Sekunden **oder** lokal `YYYY-MM-DD HH:MM`. Alle Befehle geben JSON aus.

## Migration

Alte DBs (v1: `Created`/`Uploaded`, `metric`-Tabelle) werden beim Öffnen
automatisch angepasst: fehlende Spalten kommen dazu, `Created` → `generated`,
`Uploaded` → `uploaded`, `metric` wird entfernt. Nicht-destruktiv, keine Daten
gehen verloren.
