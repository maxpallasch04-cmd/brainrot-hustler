# monitoring

Die eigenen TikTok-Metriken des Kanals abrufen und den täglichen Content-Report
bauen. Zugangsdaten + OAuth-Setup: siehe `../README.md`.

## Auth (nur einmal nötig)

Der Token liegt auf der Platte und **erneuert sich automatisch**
(`access_token()` erneuert ihn vor Ablauf), normale Befehle funktionieren also
einfach.

```
python3 -m monitoring.cli token-status                       # ist ein Token gespeichert? keine Secrets
python3 -m monitoring.cli login --print-url --redirect-uri <https-uri>
#   -> URL öffnen, autorisieren, Redirect-URL zurückkopieren:
python3 -m monitoring.cli login --redirect-uri <https-uri> --finish "<redirect-url-or-code>"
python3 -m monitoring.cli refresh                            # Refresh erzwingen
python3 -m monitoring.cli logout                             # widerrufen + löschen
```

`login` ohne Flags startet den interaktiven lokalen Server-Flow (`--manual` fügt
stattdessen die Redirect-URL ein; `--no-browser` öffnet keinen Browser).

## Daten lesen

```
python3 -m monitoring.cli user-stats                 # follower_count, likes_count, video_count
python3 -m monitoring.cli list-videos --max 50       # eigene öffentliche Videos + Metriken
```

## Täglicher Report

```
python3 -m monitoring.cli analyze --max 50 [--no-blowup]
python3 -m monitoring.cli reports --limit 5
```

`analyze` holt die neuesten Videos, gleicht sie mit `longterm_memory` ab, baut einen
Report, speichert ihn (`report`-Tabelle in derselben DB) und hängt die frischen
Metrik-Schnappschüsse an.

Report-Felder:

- `N` — im Fenster seit dem letzten Report hochgeladene Videos.
- `G` — Kanal-Summen (views / comments / likes) über die geholten Videos.
- `V_0` / `V_1` — Metriken pro Video für das aktuelle / vorherige Fenster.
- `d_global` — `(G − G′) / (G′ − G″)` aus den letzten zwei Reports.
- `d_video` — pro `V_1`-Video, `(g − m) / m` (`g` frisch, `m` neuester
  Schnappschuss).
- `blowups` — Top-`2N`-Videos nach Views-Zuwachs minus `V_0`/`V_1` (optional).
- `unmatched` — geholte Videos, die nicht zugeordnet werden konnten.

Matching: eigene Videos werden per **exaktem Titel** zu Gedächtnis-Zeilen
zugeordnet, mit Fallback auf das nächstgelegene `upload_at` (±30 min).

Alle Befehle geben JSON aus.
