# longterm_memory

Contentplan **und** Gedächtnis des Kanals in einer SQLite-Tabelle: eine Zeile pro
Video, von der Idee bis zum Upload. Dazu das Kanalprofil (Nische, Rezepte, Takt).

```
planned  --generated-->  generated  --upload-->  uploaded
```

Kein `contentplan.md`: die DB ist die Warteschlange. Eine DB für alle Kanäle,
jede Zeile trägt `channel_id`; die CLI liest den Kanal aus `bin/channel`.

## Kanalprofil

| Feld | Bedeutung |
| --- | --- |
| `id` | Kanal-ID (`a-z0-9-_`, max. 32) |
| `niche` | Nische in einem Satz |
| `art` | Standard-Videoart (`YT-Clip` \| `Twitch-Clip` \| `Selbstgeneriert`) |
| `recipes` | aktive Rezepte - andere `add-plan`s werden abgelehnt |
| `open_target` | wie viele offene Einträge es sein sollen |
| `lead_h` | Vorlauf in Stunden, ab dem generiert wird |
| `quiet_start` / `quiet_end` | Ruhezeit (`HH:MM`); leer = keine |
| `tz` | Zeitzone der Ruhezeit |
| `format` | Zielformat, z. B. `9:16,1280` |
| `r2_prefix` | Ablage-Prefix im gemeinsamen Bucket |
| `recipients` | wer Upload-Meldungen bekommt |

## Plan-Eintrag

| Feld | Bedeutung |
| --- | --- |
| `idea` | ein Satz: was ist das Video (aus der Planung) |
| `title`, `description` | Titel und Caption (erst ab `generated`) |
| `recipe`, `art`, `theme` | Herkunft und Einordnung |
| `file` | Pfad zur mp4 (`memory/<channel>/videos/...`), `NULL` bis gerendert |
| `len_s` | Länge in Sekunden, `0` bis gerendert |
| `plan_at` | geplante Uploadzeit (Unix) |
| `upload_at` | tatsächliche Uploadzeit, `NULL` bis hochgeladen |
| `status` | `planned` \| `generated` \| `uploaded` |

## CLI

```
# Plan (kanalgebunden)
bin/channel <id> longterm_memory.cli nextdue   [--lead-h 4]
bin/channel <id> longterm_memory.cli open-count
bin/channel <id> longterm_memory.cli overdue   [--now <ts>]
bin/channel <id> longterm_memory.cli add-plan  --idea "..." --recipe <name> --plan-at "2026-10-21 18:00"
bin/channel <id> longterm_memory.cli generated <id> --title "..." --file memory/<channel>/videos/x.mp4 --len-s 31
bin/channel <id> longterm_memory.cli upload    <id> [--at "2026-10-21 18:05"]
bin/channel <id> longterm_memory.cli get-video <id>
bin/channel <id> longterm_memory.cli list-videos [--status planned|generated|uploaded]

# Heartbeat (kanal-frei, alle aktiven Kanäle)
bin/cli longterm_memory.cli task [--open-target 2] [--lead-h 4]

# Kanal-Administration (kanal-frei)
bin/cli longterm_memory.cli channel-list
bin/cli longterm_memory.cli channel-get <id>
bin/cli longterm_memory.cli channel-set <id> --niche "..." --recipes a,b \
    --open-target 2 --lead-h 4 --quiet-start 22:00 --quiet-end 10:00 --tz Europe/Berlin
```

`task` liefert eine Aktion (`upload` | `pipeline` | `plan` | `idle`), den Kanal
dazu, bei `upload`/`pipeline` ein `video`-Kurzprofil (`id`, `label`,
`plan_at_local`, `file`, `status`) und eine Übersicht aller Kanäle.

`addPlan` prüft gegen das Profil: das Rezept muss aktiv sein, `plan_at` darf
nicht in der Ruhezeit liegen. `task` und `nextdue` nehmen `open_target` und
`lead_h` aus dem Profil.

Zeiten: Unix-Sekunden **oder** lokal `YYYY-MM-DD HH:MM`. Alle Befehle geben JSON aus.

## Migration

Alte DBs werden beim Öffnen angepasst: fehlende Spalten kommen dazu,
`Created` → `generated`, `Uploaded` → `uploaded`, die Metrik-Tabelle fällt weg.
Der erste angelegte Kanal übernimmt Alt-Daten ohne `channel_id`. Nicht-destruktiv.
