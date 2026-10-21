# longterm_memory

> **Aufruf:** `~/.openclaw/workspace-brainrothustler/bin/channel <id> longterm_memory.cli <cmd> <args>`
> (Workspace-Wrapper, siehe `TOOLS.md`) - aus jedem cwd, venv wird automatisch aktiviert.

Der Contentplan **und** das Gedächtnis des Kanals in einer Tabelle, plus die
Kanalprofile. Ein Eintrag pro Video, von der Idee bis zum Upload.

```
planned  --generated-->  generated  --upload-->  uploaded
```

Es gibt keine `contentplan.md` - die DB ist die Warteschlange.
DB-Pfad: `memory/brainrot.db` (überschreibbar mit `BRAINROT_DB`).

## Kanal ist Pflicht

Jede Instanz gehört genau einem Kanal:

```python
mem = LongTermMemory(channel="sls")      # ohne channel -> Fehler
mem.profile                              # Kanalprofil als dict
```

Eine DB, alle Kanäle, Spalte `video.channel_id`. Jede Query filtert hart - ein
Video von Kanal A ist für Kanal B nicht sichtbar (`KeyError`).

## Kanalprofil (`channel`-Tabelle)

| Feld | Bedeutung |
| ---- | --------- |
| `id` | Kanal-ID (`sls`, `a-z0-9-_`, max. 32) |
| `niche` | Nische in einem Satz |
| `art` | Standard-Videoart (`YT-Clip` \| `Twitch-Clip` \| `Selbstgeneriert`) |
| `recipes` | aktive Rezepte (JSON-Liste) - andere `add-plan`s werden abgelehnt |
| `open_target` | wie viele offene Einträge es sein sollen (Default 2) |
| `lead_h` | Vorlauf in Stunden, ab dem generiert wird (Default 4) |
| `quiet_start` / `quiet_end` | Ruhezeit (`22:00` / `10:00`), leer = keine |
| `tz` | Zeitzone der Ruhezeit (`Europe/Berlin`) |
| `format` | Zielformat (`9:16,1280`) |
| `r2_prefix` | Key-Prefix im geteilten Bucket (Default `brainrot/<id>/`) |
| `recipients` | Empfänger der Meldungen (JSON-Liste) |

`addPlan` prüft **gegen das Profil**: Rezept muss aktiv sein, `plan_at` darf nicht
in der Ruhezeit liegen. `task` nimmt `open_target` und `lead_h` aus dem Profil.

## Video-Felder

| Feld | Bedeutung |
| ---- | --------- |
| `channel_id` | Kanal |
| `idea` | ein Satz: was ist das Video (aus der Planung) |
| `title` | finaler Titel (erst ab `generated`) |
| `description` | Caption fürs Upload (erst ab `generated`) |
| `art`, `recipe`, `theme` | Art, Rezept-ID, Thema |
| `file` | Pfad zur mp4 (`memory/<channel>/videos/...`), `NULL` bis gerendert |
| `len_s` | Länge in Sekunden, `0` bis gerendert |
| `plan_at` | **geplante** Uploadzeit (Unix) |
| `upload_at` | tatsächliche Uploadzeit (Unix), `NULL` bis hochgeladen |
| `status` | `planned` \| `generated` \| `uploaded` |

## Python-API

```python
from longterm_memory import LongTermMemory

mem = LongTermMemory(channel="sls")
vid = mem.addPlan("Best Trick, Score 9.10", "ytsls-besttrick", plan_at=1793000000)
mem.markGenerated(vid, title="Insane 9.10 Best Trick", description="...",
                  file="memory/sls/videos/besttrick.mp4", len_s=31)
mem.upload(vid)                 # -> uploaded, setzt upload_at (idempotent)
mem.task()                      # {'action': 'upload'|'pipeline'|'plan'|'idle', ...}
mem.nextDue()                   # nächster fälliger planned-Eintrag
mem.openCount()                 # planned + generated
mem.overdue()                   # generated, Uploadzeit vorbei
```

| Methode | Zweck |
| ------- | ----- |
| `addPlan(idea, recipe, plan_at, art=None, theme="")` | Plan-Eintrag anlegen (`planned`) → id; validiert gegen Profil |
| `markGenerated(id, *, title, description, file, len_s, art=None, theme=None)` | Render eintragen (`generated`) |
| `upload(id, at=None)` | als `uploaded` markieren, `upload_at` setzen (idempotent) |
| `getVideo(id)` / `listVideos(status=None)` | lesen, nach `plan_at` sortiert |
| `openCount()` | offene Einträge (`planned` + `generated`) |
| `nextDue(now=None, lead_s=None)` | nächster fälliger `planned`-Eintrag oder `None` |
| `overdue(now=None)` | `generated`, deren Uploadzeit vorbei ist |
| `task(now=None, lead_s=None, open_target=None)` | eine Heartbeat-Entscheidung: `upload` \| `pipeline` \| `plan` \| `idle` |
| `task_all(path=None, *, now=None, lead_s=None, open_target=None)` | dasselbe über **alle aktiven Kanäle**; liefert die dringendste Aktion + `channel` und `channels` (Übersicht). Ohne Kanal: `ChannelError` |

## CLI

```
bin/cli longterm_memory.cli task [--open-target 2] [--lead-h 4] [--now "2026-10-21 18:00"]   # kanal-frei
bin/channel sls longterm_memory.cli add-plan --idea "..." --recipe ytsls-besttrick --plan-at "2026-10-21 18:00"
bin/channel sls longterm_memory.cli nextdue [--lead-h 4]
bin/channel sls longterm_memory.cli open-count
bin/channel sls longterm_memory.cli generated 1 --title "..." --file memory/sls/videos/x.mp4 --len-s 31
bin/channel sls longterm_memory.cli overdue
bin/channel sls longterm_memory.cli upload 1 [--at "2026-10-21 18:05"]
bin/channel sls longterm_memory.cli get-video 1
bin/channel sls longterm_memory.cli list-videos [--status planned|generated|uploaded]

# Profile (channel-set/get brauchen --channel)
bin/cli longterm_memory.cli channel-list
bin/cli longterm_memory.cli channel-get sls
bin/cli longterm_memory.cli channel-set sls --niche "Skate comps" \
    --recipes ytsls-besttrick,ytsls-bestline --open-target 2 --lead-h 4 \
    --quiet-start 22:00 --quiet-end 10:00 --tz Europe/Berlin
```

`task` ist der Herzstück-Befehl für den Heartbeat - eine Antwort, eine Aktion,
**kanal-frei** (entscheidet über alle aktiven Kanäle):

```json
{"action": "pipeline", "channel": "sls", "open": 2, "target": 2,
 "entry": {"id": 3, ...},
 "video": {"id": 3, "label": "Best Trick 9.10 (#3)", "title": "",
           "idea": "Best Trick 9.10", "recipe": "ytsls-besttrick", "file": null,
           "plan_at": 1793000000, "plan_at_local": "2026-10-21 18:00", "status": "planned"},
 "channels": [{"channel": "sls", "action": "pipeline", "open": 2, "target": 2},
              {"channel": "second", "action": "idle", "open": 2, "target": 2}]}
```

`video` beantwortet „um welches Video geht es": bei `pipeline` der fällige Eintrag,
bei `upload` das dringendste aus `videos`, bei `plan`/`idle` fehlt es.
`plan_at_local` ist bereits in der Kanal-Zeitzone formatiert.

Priorität: `upload` → `pipeline` → `plan` → `idle`. Ausgegeben wird **nur** die
Aktion, die jetzt dran ist; `entry` und `videos` sind dabei, wenn sie existieren.
Was später ansteht, kommt im nächsten Heartbeat von selbst. Gibt es keinen
Kanal, endet `task` mit `ChannelError` statt mit `idle`.

Zeiten: Unix-Sekunden **oder** lokal `YYYY-MM-DD HH:MM`. Alle Befehle geben JSON aus.

**Debug:** `--now` friert die Bezugszeit ein (bei `task`, `nextdue`, `overdue`) -
damit lässt sich ein Heartbeat reproduzieren, ohne zu warten. `--open-target` und
`--lead-h` überschreiben die Profilwerte für einen Lauf.

## Migration

Alte DBs werden beim Öffnen automatisch angepasst: fehlende Spalten kommen dazu,
`Created` → `generated`, `Uploaded` → `uploaded`, `metric` wird entfernt. Der
**erste** angelegte Kanal übernimmt Alt-Daten ohne `channel_id`. Nicht-destruktiv.
