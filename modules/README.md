# BrainrotHustler Module

Python-Module, die der Agent per `exec` steuert. Jedes Modul hat ein eigenes
README, das beschreibt, **wie man seine Schnittstelle benutzt**; diese Datei deckt
das **Setup** ab (Module ausführen + Umgebung / Secrets).

## Ausführen

Jeden Befehl mit **diesem Ordner** als Arbeitsverzeichnis ausführen oder ihn auf
`PYTHONPATH` legen:

```
cd <workspace>/modules
python3 -m monitoring.cli analyze
```

Veränderlicher Zustand liegt unter `data/` (SQLite-DB + Token-Datei), Downloads
unter `clips/`.

## Module

| Modul              | Zweck                                                              |
| ------------------ | ------------------------------------------------------------------ |
| `longterm_memory`  | SQLite-Gedächtnis: Videos + Metrik-Schnappschüsse                  |
| `video_generation` | cut / background / overlay / audio / concat / render               |
| `twitch_clips`     | virale Twitch-Clips finden + herunterladen                         |
| `monitoring`       | TikTok-Metriken + täglicher Content-Report                         |
| `hosting`          | eine Datei hochladen, öffentliche URL bekommen (catbox/litterbox)  |

## Installation

```
python3 -m pip install moviepy pillow requests yt-dlp
```

Benötigt Python 3.11+.

## Umgebung / Secrets

Als Umgebungsvariablen setzen (Betreiberseite, z. B.
`openclaw config set env.vars.<NAME> "<value>"`). Secrets werden nie in Dateien
gespeichert.

### `longterm_memory`

| Var           | Nötig | Bedeutung                                  |
| ------------- | ----- | ------------------------------------------ |
| `BRAINROT_DB` | nein  | SQLite-Pfad. Standard `data/brainrot.db`.  |

### `video_generation`

Keine Umgebungsvariablen.

### `twitch_clips`

| Var                    | Nötig | Bedeutung                 |
| ---------------------- | ----- | ------------------------- |
| `TWITCH_CLIENT_ID`     | ja*   | Twitch-App Client ID      |
| `TWITCH_CLIENT_SECRET` | ja*   | Twitch-App Client Secret  |

\* Nötig für `game-id` und `clips`; `download` braucht keine.

Beziehen (einmalig): auf <https://dev.twitch.tv/console/apps> einloggen (2FA am
Account) → **Register Your Application** (Name egal, OAuth Redirect URL
`http://localhost` — ungenutzt, Category `Application Integration`, Client Type
`Confidential`) → **Client ID** kopieren, dann **New Secret** → **Client Secret**
kopieren (wird einmal angezeigt).

### `monitoring`

| Var                     | Nötig | Bedeutung                                                                   |
| ----------------------- | ----- | --------------------------------------------------------------------------- |
| `TIKTOK_CLIENT_KEY`     | ja*   | TikTok Developer App client key                                             |
| `TIKTOK_CLIENT_SECRET`  | ja*   | TikTok Developer App client secret                                          |
| `TIKTOK_REDIRECT_URI`   | nein  | Registrierte https-Redirect-URI (Standard `http://localhost:8080/callback`) |
| `TIKTOK_SCOPE`          | nein  | Standard `user.info.basic,user.info.stats,video.list`                       |
| `TIKTOK_ACCESS_TOKEN`   | nein  | Statischer Token; überspringt den OAuth-Flow                                |
| `TIKTOK_TOKEN_FILE`     | nein  | Token-Datei. Standard `data/tiktok_token.json`                              |

\* Nötig, außer es ist ein statischer `TIKTOK_ACCESS_TOKEN` gesetzt.

TikTok Developer App (einmalig): **Login Kit** + **Display API** aktivieren; die
oben genannten Scopes hinzufügen; die Redirect-URI registrieren (**nur https**);
den eigenen TikTok-Account als Testnutzer hinzufügen. Dann einmal
`python3 -m monitoring.cli login` ausführen (siehe Modul-README). Der Access-Token
(24 h) wird automatisch aus dem gespeicherten Refresh-Token (365 d) erneuert.

**Token setzen.** Zwei Wege — keiner legt das Secret in verfolgte Dateien dieses
Ordners:

- **Statischer Token per Env (bevorzugt).**
  ```
  openclaw config set env.vars.TIKTOK_ACCESS_TOKEN "<access-token>"
  openclaw config set env.vars.TIKTOK_CLIENT_KEY "<client-key>"
  openclaw config set env.vars.TIKTOK_CLIENT_SECRET "<client-secret>"
  ```
  Ein statischer `TIKTOK_ACCESS_TOKEN` überspringt den OAuth-Flow.
- **Einmaliger OAuth-Flow** (`python3 -m monitoring.cli login`). Der erneuerte Token
  wird nach `data/tiktok_token.json` (`TIKTOK_TOKEN_FILE`) geschrieben — diese
  Datei ist **Runtime-State** mit Access- + Refresh-Token. Raus aus Build/Repo
  halten (gitignore/löschen vor dem Ausliefern) und nie zwischen Maschinen kopieren.

Hinweis: Die aktuell im Build liegende `data/tiktok_token.json` ist solcher
Runtime-State — bis zum Widerruf als geleaktes Secret behandeln.

### `hosting`

Keine Umgebungsvariablen (anonym). Optionaler `userhash` je Aufruf.
