# BrainrotHustler 🤖

Agent, der automatisiert einen TikTok-Kanal betreibt: planen → produzieren →
Upload melden → analysieren. **Den Upload macht der Mensch.**

Die Workspace-Dateien des Agenten liegen in `agent/`, die Grenzen setzt
OpenClaw über die Config-Dateien in `setup/`.

---

## 1. Repo-Layout

```
agent/     → Workspace-Dateien des Agenten (inkl. Code unter modules/)
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

> `setup/` erst **nach** dem Config-Patch entfernen — Reihenfolge in §4.

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
├── modules/
├── recipes/
└── skills/
```

> `agents.entries.brainrothustler.workspace` muss auf genau diesen Pfad zeigen
> (`~/.openclaw/workspace-brainrothustler`) — die Dateien liegen direkt darin.

> **Bewusst kein `.git` im Workspace.** Der Agent schreibt `MEMORY.md`, `memory/`
> und Token/DBs unter `modules/data/` zur Laufzeit. In einem Git-Arbeitsbaum
> gibt das Dreck-Status, Pull-Konflikte und macht `git clean`/`git pull`
> gefährlich für Laufzeit- und Token-Daten. Die Workspace-Dateien sind ein
> **Deploy-Snapshot**, kein Repo.

> **Laufzeit-Daten beim Update stehen lassen:** `MEMORY.md`, `memory/` und
> `modules/data/` (Token, SQLite-DBs) sind lokal und **nicht** Teil des Deploys —
> beim Update nicht überschreiben.

---

## 3. Zugänge

R2-Credentials (`R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`,
`R2_BUCKET`, `R2_PUBLIC_BASE_URL`) liegen als **`env`-Kind im OpenClaw-Store**,
nicht in einer `.env`. Sie werden Gateway-gehostetem `exec` automatisch als
Umgebungsvariablen injiziert → `modules/hosting` liest `os.environ`.

> Für Kontexte **außerhalb** des Gateways (Sandbox/remote/anderer Host) reicht
> das nicht — dort braucht es eine eigene `.env` neben `modules/`.

---

## 4. Setup (Linux)

```bash
# 1) Repo ins OpenClaw-Verzeichnis klonen (siehe Verzeichniswechsel)
git clone <repo-url> ~/.openclaw/workspace-brainrothustler
cd ~/.openclaw/workspace-brainrothustler

# 2) Workspace-Dateien an ihren Platz
cp -a agent/. .
rm -rf agent

# 3) Berechtigungen schreiben (setup/ liegt noch im Verzeichnis)
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

# 4) Prüfen und anwenden
openclaw config get agents.entries.brainrothustler.tools
openclaw exec-policy show --agent brainrothustler
openclaw approvals get --gateway

# 5) Aufräumen: Repo-Rest weg, Workspace = nur die Agent-Dateien
rm -rf setup .git

openclaw gateway restart
```

Anschließend Telegram binden (eigener Bot-Account, Chat-ID = Owner).
Heartbeat: stündlich 09:00–22:00 (`lightContext`, isolierte Session).

---

## 5. Status

- Agent-Workspace-Struktur: steht (`agent/`).
- `setup/agent-config.json`: steht (Agent, Tools, `exec.mode: ask`, Heartbeat).
- `setup/exec-approvals.json`: steht als **Entwurf** — Allowlist über die
  Modul-CLIs (`python3 -m <modul>.cli …`); **partieller Patch** (nur
  `agents.brainrothustler`), vor dem Einspielen mergen — Details in `setup/README.md`.
- `agent/BOOTSTRAP.md` ist noch im Repo → ein Deploy startet das Onboarding
  erneut; vor dem ersten Deploy löschen oder bewusst behalten.

Verhalten und Grenzen des Agenten: `agent/AGENTS.md`.
