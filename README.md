# BrainrotHustler 🤖

Agent, der automatisiert einen TikTok-Kanal betreibt: planen → produzieren →
Upload melden → analysieren. **Den Upload macht der Mensch.**

Die Workspace-Dateien des Agenten liegen in `agent/`, die Grenzen setzt
OpenClaw über die Config-Dateien in `setup/`.

---

## 1. Repo-Layout

```
agent/     → Workspace-Dateien des Agenten (inkl. Code unter modules/ + Wrapper bin/cli)
setup/     → Config-Dateien (setzen die Berechtigungen)
README.md
```

`agent/README.md` beschreibt den Inhalt des Agent-Workspaces (Standing Orders,
Skills, Rezepte, Module, Assets).

---

## 2. Verzeichniswechsel

**Ziel auf dem VPS:** das Repo wird **direkt ins OpenClaw-Workspace-Verzeichnis
geklont**. Danach wird der komplette Inhalt von `agent/` in den Workspace-Root
kopiert, der Repo-Rest wird entfernt:

```bash
git clone <repo-url> ~/.openclaw/workspace-brainrothustler
cd ~/.openclaw/workspace-brainrothustler
cp -a agent/. .
rm -rf agent
```

> `setup/` erst **nach** dem Config-Patch entfernen — Reihenfolge in §5.

Ergebnis (Endzustand):

```
~/.openclaw/workspace-brainrothustler/   ← Agent-Workspace
├── AGENTS.md
├── BOOTSTRAP.md
├── HEARTBEAT.md
├── IDENTITY.md
├── SOUL.md
├── TOOLS.md
├── USER.md
├── contentplan.md
├── assets/
├── bin/            ← cli — Modul-Wrapper (einziger erlaubter Aufrufweg)
├── modules/
├── recipes/
├── skills/
└── .venv/          ← nur VPS: venv (nicht committen / nicht überschreiben)
```

> `agents.entries.brainrothustler.workspace` muss auf genau diesen Pfad zeigen
> (`~/.openclaw/workspace-brainrothustler`) — die Dateien liegen direkt darin.

> **Bewusst kein `.git` im Workspace.** Der Agent schreibt `MEMORY.md`, `memory/`
> und Token/DBs unter `modules/data/` zur Laufzeit. In einem Git-Arbeitsbaum
> gibt das Dreck-Status, Pull-Konflikte und macht `git clean`/`git pull`
> gefährlich für Laufzeit- und Token-Daten. Die Workspace-Dateien sind ein
> **Deploy-Snapshot**, kein Repo.

> **Laufzeit-Daten beim Update stehen lassen:** `MEMORY.md`, `memory/`,
> `modules/data/` (Token, SQLite-DBs) und `.venv/` (VPS) sind lokal und **nicht**
> Teil des Deploys — beim Update nicht überschreiben.

---

## 3. Zugänge

R2-Credentials (`R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`,
`R2_BUCKET`, `R2_PUBLIC_BASE_URL`) liegen als **`env`-Kind im OpenClaw-Store**,
nicht in einer `.env`. Sie werden Gateway-gehostetem `exec` automatisch als
Umgebungsvariablen injiziert → `modules/hosting` liest `os.environ`.

> Für Kontexte **außerhalb** des Gateways (Sandbox/remote/anderer Host) reicht
> das nicht — dort braucht es eine eigene `.env` neben `modules/`.

**YouTube-Cookies** (für `yt_clips`) sind ebenfalls ein Zugang: YouTube blockt
Rechenzentrums-IPs („Sign in to confirm you're not a bot"). Eine Netscape-
`cookies.txt` liegt auf dem Host **außerhalb** von Workspace/Repo — Default
`~/.openclaw/state/brainrot/cookies.txt` (`BRAINROT_STATE_DIR` verschiebt das
Verzeichnis), Pfad überschreibbar via `YTDLP_COOKIES_FILE`. yt-dlp schreibt sie
beim Lauf zurück (beschreibbar halten). Ohne Cookies scheitert der YT-Download.

### YouTube: PO-Token-Provider (optional — nur bei IP-Sperre)

Cookies heilen den Bot-Check, **nicht** eine Sperre der IP/ASN. Dagegen hilft der
PO-Token-Provider `bgutil-ytdlp-pot-provider`; die empfohlene Kombi ist Provider
**+** Cookies. Er läuft auf der VPS **nativ mit Node — kein Docker nötig**: der
langsame Weg ist der *Script*-Modus (neuer Node-Prozess pro Aufruf), der
*Server*-Modus ist schnell und ebenfalls reines Node. Docker wäre nur eine zweite
Zustellform desselben Servers.

Voraussetzungen: `node >= 22` (`node --version`!), `npm >= 9`,
`yt-dlp >= 2025.05.22`. Version **≥ 2.0.0** nehmen — davor hatte der Server eine
RCE (GHSA-qpv9-8xfj-xx9m); seit 2.0.0 bindet er nur noch auf localhost.

```bash
# 1) Plugin in DIE venv, die der Wrapper benutzt
~/.openclaw/workspace-brainrothustler/.venv/bin/pip install -U bgutil-ytdlp-pot-provider

# 2) Provider bauen (Version = Plugin-Version)
# Einzeilig halten — ein '\'-Umbruch wird beim Einfügen zu einem Leerzeichen
# vor der URL ("protocol ' https' is not supported").
rm -rf ~/bgutil-ytdlp-pot-provider   # falls ein abgebrochener Clone-Rest liegt
git clone --single-branch --branch 2.0.2 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git ~/bgutil-ytdlp-pot-provider
cd ~/bgutil-ytdlp-pot-provider/server && npm ci && npx tsc
```

Dauerbetrieb als **systemd-User-Service**. Der `ExecStart`-Pfad wird aus
`command -v node` gefüllt — Systemd findet ein nvm-Node sonst nicht:

```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/bgutil.service <<EOF
[Unit]
Description=bgutil PO token provider

[Service]
ExecStart=$(command -v node) %h/bgutil-ytdlp-pot-provider/server/build/main.js
WorkingDirectory=%h/bgutil-ytdlp-pot-provider/server
Restart=always

[Install]
WantedBy=default.target
EOF
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now bgutil
loginctl enable-linger "$USER"      # läuft auch ohne Login-Session
```

Läuft der Server auf `127.0.0.1:4416` (Default), braucht yt-dlp **keine**
Konfiguration. Prüfen:

```bash
python3 -m yt_dlp -v "<url>" 2>&1 | grep -E "PO Token Providers|Generating"
# erwartet:  [pot] PO Token Providers: bgutil:http-2.0.2 (external)
#            [pot:bgutil:http] Generating a gvs PO Token for web client ...
```

Kommt trotz Provider weiter der Bot-Check, Client wechseln (env, siehe `TOOLS.md`):
`YTDLP_EXTRACTOR_ARGS="youtube:player_client=mweb,tv,web_safari"`.

> Den Server **nicht** auf `0.0.0.0` binden (`-H`/`-p` nicht verändern) — er ist
> unauthentifiziert. Notnagel, falls `npm ci` an `canvas` scheitert: das
> Docker-Image `brainicism/bgutil-ytdlp-pot-provider` mit
> `-p 127.0.0.1:4416:4416` (oder Deno statt Node).

---

## 4. Python-Umgebung & Abhängigkeiten

Die Module sind reines Python (kein Paket, keine Installation nötig — sie laufen
aus dem Workspace).

**VPS: eigener venv.** Er liegt im Workspace-Root als `.venv/`
(`~/.openclaw/workspace-brainrothustler/.venv`) — **nicht** committen und beim
Update nicht überschreiben (wie `modules/data/`).

**Windows/MaxLaptop (verifiziert): kein venv** — die Module laufen gegen den
Host-Python (3.14, `C:\Program Files\Python314`), Pakete im User-sitepackages
`%APPDATA%\Python\Python314`.

Fremdpakete (alles andere ist stdlib):

| Modul | Braucht |
|---|---|
| `hosting` | `boto3`, `requests` |
| `twitch_clips` | `yt-dlp` |
| `yt_clips` | `yt-dlp`, `moviepy`, `numpy`, `Pillow` |
| `video_generation` | `moviepy`, `numpy`, `Pillow` |
| `subtitles` | `imageio-ffmpeg` (bringt das ffmpeg-Binary mit) |
| `longterm_memory`, `monitoring` | — (nur stdlib) |

VPS einrichten (genau einmal, aus dem Workspace-Root):

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r modules/requirements.txt
```

**Aufrufweg für den Agenten ist der Wrapper `bin/cli`.** Er aktiviert die venv und
wechselt selbst nach `modules/` — Module werden nur so aufgerufen (siehe
`agent/TOOLS.md`):

```bash
~/.openclaw/workspace-brainrothustler/bin/cli hosting.cli usage
```

> `exec` ist **nicht interaktiv**: `source .venv/bin/activate` wirkt dort nicht,
> und `python3 -m …` direkt aufzurufen ist nicht erlaubt. Darum läuft alles über
> den Wrapper — **er** steht in der exec-Allowlist (`setup/exec-approvals.json`),
> nicht der Interpreter.

Zum Entwickeln/Testen von Hand geht weiterhin der venv-Interpreter direkt (aus
`modules/`):

```bash
cd modules
../.venv/bin/python3 -m hosting.cli usage
```

Windows (kein venv): `python -m pytest modules/tests` bzw. `python -m hosting.cli …`.
`ffmpeg` liefert `imageio-ffmpeg` selbst; ein System-`ffmpeg` ist optional.

---

## 5. Setup (Linux)

```bash
# 1) Repo ins OpenClaw-Verzeichnis klonen (siehe Verzeichniswechsel)
git clone <repo-url> ~/.openclaw/workspace-brainrothustler
cd ~/.openclaw/workspace-brainrothustler

# 2) Workspace-Dateien an ihren Platz
cp -a agent/. .
rm -rf agent
chmod +x bin/cli            # Wrapper muss ausführbar sein

# 3) venv anlegen + Modul-Abhängigkeiten (VPS)
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r modules/requirements.txt

# 4) Berechtigungen schreiben (setup/ liegt noch im Verzeichnis)
openclaw config patch --file setup/agent-config.json

#    ACHTUNG: `approvals set` ERSETZT das gesamte Dokument (host-weit, alle
#    Agenten; `defaults`/`socket` inklusive). Darum erst holen, mergen, setzen:
openclaw approvals get --gateway --json | jq '.file' > /tmp/approvals.current.json
jq --slurpfile new setup/exec-approvals.json \
   '.agents = (.agents * $new[0].agents)' /tmp/approvals.current.json \
   > /tmp/approvals.merged.json
openclaw approvals set --gateway --file /tmp/approvals.merged.json
#    (ohne jq: /tmp/approvals.current.json editieren und den Block
#     agents.brainrothustler aus setup/exec-approvals.json von Hand einsetzen)

# 5) Prüfen und anwenden
openclaw config get agents.entries.brainrothustler.tools
openclaw exec-policy show --agent brainrothustler
openclaw approvals get --gateway
#    Allowlist muss den Wrapper enthalten (~/.openclaw/workspace-brainrothustler/bin/cli)

# 6) Aufräumen: Repo-Rest weg, Workspace = nur die Agent-Dateien
#    (.venv/ bleibt stehen!)
rm -rf setup .git modules/requirements.txt README.md

openclaw gateway restart
```

Anschließend Telegram binden (eigener Bot-Account, Chat-ID = Owner).
Heartbeat: stündlich 09:00–22:00 (`lightContext`, isolierte Session).

---

## 6. Status

- Agent-Workspace-Struktur: steht (`agent/`).
- `setup/agent-config.json`: steht (Agent, Tools, `exec.mode: ask`, Heartbeat).
- `setup/exec-approvals.json`: steht — die Allowlist bindet **den Wrapper**
  (`~/.openclaw/workspace-brainrothustler/bin/cli`) mit einem `argPattern` über die
  Modul-CLIs. Der Interpreter steht **nicht** mehr drin (der Wrapper aktiviert die
  venv selbst) — damit ist der Wrapper das einzige erlaubte Einstiegstoken.
  **Partieller Patch** (nur `agents.brainrothustler`), vor dem Einspielen mergen.
- `agent/bin/cli`: Modul-Wrapper (venv aktivieren → `python3 -m "$@"` aus
  `modules/`). Muss im Deploy **ausführbar** sein (`chmod +x bin/cli`).
- **YouTube-Cookies**: liegen außerhalb des Repos
  (`~/.openclaw/state/brainrot/cookies.txt`) und sind **nicht** Teil des Deploys —
  pro Host einmalig bereitstellen, sonst scheitert der YT-Download am Bot-Schutz.
- **PO-Token-Provider** (`bgutil`, optional): nur nötig, wenn die VPS-IP selbst
  geblockt ist — dann helfen Cookies nicht. Läuft nativ mit Node ≥ 22 als
  systemd-User-Service, **kein Docker** (Anleitung in §3).
- `agent/BOOTSTRAP.md` ist noch im Repo → ein Deploy startet das Onboarding
  erneut; vor dem ersten Deploy löschen oder bewusst behalten.

Verhalten und Grenzen des Agenten: `agent/AGENTS.md`.
