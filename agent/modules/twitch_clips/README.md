# twitch_clips

Virale Twitch-Clips für eine Kategorie finden und herunterladen.

Einschränkungen, die die Abfrage beeinflussen:

- **Keine Volltextsuche.** Du grenzt Clips per Kategorie (`--game` / `--game-id`)
  oder Broadcaster ein, optional in einem Zeitfenster — dann filtern/shortlisten.
- Ergebnisse kommen **meistgesehen zuerst** zurück.
- `--sort views` = bewährte Hits; `--sort velocity` = frisch viral
  (views pro Stunde). Clips brauchen meist Tage, um viral zu gehen, also lieber
  `--hours` weiten (z. B. `168`) statt große 24-h-Zahlen zu erwarten.
- `--state <file>` hält ein JSON-Set bereits gesehener Clip-IDs und schließt sie
  aus, sodass wiederholte Läufe nur neue Clips zeigen.

## CLI

```
python3 -m twitch_clips.cli game-id --name "Fortnite"
python3 -m twitch_clips.cli clips --game "Fortnite" --hours 168 --min-views 5000 \
    --top 10 --sort velocity --state data/twitch_seen.json

python3 -m twitch_clips.cli download --id <clip-id> --out-dir clips
python3 -m twitch_clips.cli download --url <clip-url>
python3 -m twitch_clips.cli clips ... | python3 -m twitch_clips.cli download --from-json -
```

`clips`-Optionen: `--game` / `--game-id`, `--hours`, `--min-views`,
`--max-duration`, `--language`, `--top`, `--sort views|velocity`, `--max-pages`,
`--state`.

`download` akzeptiert `--url`, `--id` oder `--from-json` (das `clips`-Ausgabeobjekt
`{"clips": [...]}`, eine bloße Liste oder `-` für stdin aus einer Pipe). Dateien
landen in `--out-dir/<clip-id>.mp4`; vorhandene Dateien werden übersprungen, außer
`--overwrite`. Ausgabe: `{downloaded, skipped, failed}`.

Alle Befehle geben JSON aus.

## Python-API

```python
from twitch_clips import Helix, find_clips, download_clips

client = Helix()
clips = find_clips(client, game="Fortnite", hours=24, min_views=5000,
                   top=10, sort="velocity")
for c in clips:
    print(c["url"], c["view_count"], c["views_per_hour"])

paths = download_clips(clips, out_dir="clips", top=3)
```
