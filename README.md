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
- `agent/BOOTSTRAP.md` ist noch im Repo → ein Deploy startet das Onboarding
  erneut; vor dem ersten Deploy löschen oder bewusst behalten.

Verhalten und Grenzen des Agenten: `agent/AGENTS.md`.
