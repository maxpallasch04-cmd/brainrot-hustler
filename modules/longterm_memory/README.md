# longterm_memory

Dauerhafter Speicher für die Videos des Kanals und ihre Metrik-Schnappschüsse —
das Langzeitgedächtnis des Agenten. `monitoring` schreibt hinein; die
Content-Planung liest daraus.

DB-Pfad: siehe `../README.md`.

## Python-API

```python
from longterm_memory import LongTermMemory, VideoArt

mem = LongTermMemory()
vid = mem.addVideo("title", VideoArt.TWITCH_CLIP, len_s=30, theme="csgo",
                   recipe="twitchkatze")
mem.upload(vid)                               # status -> Uploaded, setzt upload_at
mem.addMetric(vid, views=1200, comments=30, likes=90)
mem.newestMetric(vid)                         # {'ts':..., 'views':1200, ...}
```

`art` ∈ {`Selbstgeneriert`, `Twitch-Clip`, `Geklaut`, `Serien-Clip`}; status ∈
{`Created`, `Uploaded`}; `upload_at` ist bis zum Upload `NULL`. Zeitstempel sind
Unix-Epoch-Sekunden. `recipe` ist der Rezeptname (`recipes/<name>.md`), aus dem das
Video gebaut wurde — genutzt für die Analyse pro Rezept.

| Methode | Zweck |
| ------- | ----- |
| `addVideo(title, art, len_s, description="", theme="", recipe="", created_at=None)` | Video einfügen (Created) → id |
| `upload(id, at=None)` | als Uploaded markieren, `upload_at` setzen (idempotent) |
| `addMetric(id, views, comments, likes, ts=None)` | Schnappschuss anhängen (gleicher ts überschreibt) |
| `newestMetric(id)` | neuester Schnappschuss → dict / None |
| `getVideo(id)` / `listVideos(status=None)` | Videos lesen |
| `listMetrics(id, limit=None)` | Metrik-Verlauf, ältestes zuerst |
| `videosUploadedSince(ts)` | Uploads ab `ts` |
| `totalSince(ts)` | summierte Metriken über Schnappschüsse ab `ts` (G) |

## CLI

```
python3 -m longterm_memory.cli add-video --title "t" --art "Twitch-Clip" --len-s 30 \
    --theme "cats" --recipe "twitchkatze"
python3 -m longterm_memory.cli get-video 1
python3 -m longterm_memory.cli list-videos [--status Created|Uploaded]
python3 -m longterm_memory.cli upload 1 [--at <unix_ts>]
python3 -m longterm_memory.cli add-metric 1 1200 30 90 [--ts <unix_ts>]
python3 -m longterm_memory.cli newest-metric 1
```

Alle Befehle geben JSON aus.
