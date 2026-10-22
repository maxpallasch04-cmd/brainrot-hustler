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
├── assets/
├── bin/            ← cli — Modul-Wrapper (einziger erlaubter Aufrufweg)
├── memory/         ← Laufzeit: alles, was der Agent produziert
│   ├── brainrot.db ← Kanäle + Contentplan + Video-Gedächtnis (eine DB)
│   └── <channel>/  ← pro Kanal: videos/, clips/, screenshots/, specs/
├── modules/        ← nur Code
├── recipes/
├── skills/
└── .venv/          ← nur VPS: venv (nicht committen / nicht überschreiben)
```

> `agents.entries.brainrothustler.workspace` muss auf genau diesen Pfad zeigen
> (`~/.openclaw/workspace-brainrothustler`) — die Dateien liegen direkt darin.

> **Bewusst kein `.git` im Workspace.** Der Agent schreibt `MEMORY.md` und den
> kompletten `memory/`-Ordner (Videos, Clips, Screenshots, Specs, DB) zur
> Laufzeit. In einem Git-Arbeitsbaum gibt das Dreck-Status, Pull-Konflikte und
> macht `git clean`/`git pull` gefährlich für Laufzeit-Daten. Die
> Workspace-Dateien sind ein **Deploy-Snapshot**, kein Repo.

> **Laufzeit-Daten beim Update stehen lassen:** `MEMORY.md`, `memory/` (inkl.
> `brainrot.db`) und `.venv/` (VPS) sind lokal und **nicht** Teil des Deploys —
> beim Update nicht überschreiben. Videos können GBs groß sein.

---

## 3. Kanäle

Ein Agent kann mehrere Kanäle betreiben. **Kanalspezifisch ist alles in der DB**, nicht
in Markdown: eine `channel`-Zeile pro Kanal (Nische, aktive Rezepte, Upload-Takt,
Ruhezeiten, Zeitzone, Format, R2-Prefix, Empfänger).

- Kanal wird beim Aufruf gesetzt: `bin/channel <id> ...` setzt `BRAINROT_CHANNEL`.
  Es gibt **keinen** Session-Zustand und keinen „aktuellen Kanal" - der Kanal ist
  pro Aufruf explizit.
- Eine DB für alle Kanäle (`memory/brainrot.db`), Spalte `channel_id`; jede Query
  ist kanalgebunden. Dateien liegen pro Kanal unter `memory/<channel>/`.
- `add-plan` validiert gegen das Profil: Rezept muss aktiv sein, Uploadzeit darf
  nicht in der Ruhezeit liegen.
- R2: **ein Bucket für alle Kanäle**, getrennt nur durch den Prefix
  (`brainrot/<channel>/`). `hosting` liest ihn aus dem Kanalprofil;
  `R2_KEEP`/Aufräumen wirkt pro Prefix.
- `editor` braucht keinen Kanal (reine Funktion); `hosting` nur für den Prefix.

```
bin/cli longterm_memory.cli channel-list
bin/cli longterm_memory.cli channel-get sls
```

---

## 4. Zugänge

R2-Credentials (`R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`,
`R2_BUCKET`, `R2_PUBLIC_BASE_URL`) liegen als **`env`-Kind im OpenClaw-Store**,
nicht in einer `.env`. Sie werden Gateway-gehostetem `exec` automatisch als
Umgebungsvariablen injiziert → `modules/hosting` liest `os.environ`.

> Für Kontexte **außerhalb** des Gateways (Sandbox/remote/anderer Host) reicht
> das nicht — dort braucht es eine eigene `.env` neben `modules/`.

### Umgebungsvariablen

Alles, was zur Laufzeit über die Umgebung gesteuert wird. Für den Agenten
irrelevant - er ruft nur `bin/cli` / `bin/channel` auf.

| Variable | Bedeutung | Default |
| --- | --- | --- |
| `BRAINROT_CHANNEL` | aktiver Kanal; setzt `bin/channel` | - |
| `BRAINROT_DB` | Pfad der SQLite-DB | `memory/brainrot.db` |
| `WHISPER_MODEL` | Default-Modell fürs Transkript (`tiny` … `large-v3`) | `base` |
| `WHISPER_MODEL_DIR` | Modell-Cache, z. B. außerhalb des Home | Hugging-Face-Cache |
| `TESSERACT_CMD` | Tesseract-Binary für OCR | `tesseract` im PATH |
| `R2_*` | Zugänge, Bucket, Public-URL (siehe oben) | - |
| `R2_KEEP` / `R2_QUOTA_GB` | Aufbewahrung je Prefix | `1` / `10 GB` |
| `EDITOR_FFMPEG` / `EDITOR_FFPROBE` | eigenes Binary statt `imageio-ffmpeg` | - |

### Video-Übergabe (kein Download auf dem Host)

YouTube blockt Rechenzentrums-IPs („Sign in to confirm you're not a bot"), deshalb
lädt **der Operator** im Browser: `request` schickt den Link raus, er legt die
Datei (1080p, mp4) in den R2-Bucket, `fetch` holt sie von dort. Keine Cookies,
kein PO-Token-Provider, kein yt-dlp — der Host braucht dafür keine Zugänge.

### Operator-Werkzeug: `fetch-upload.py`

Im Projekt-Root, für dich — nicht für den Agenten. Lädt das Video in guter
Qualität (1080p DASH + Audio, per ffmpeg gemerged) und legt es direkt in den
Bucket; gibt die öffentliche URL als JSON aus.

```bash
python fetch-upload.py "https://youtu.be/<id>" --channel sls
python fetch-upload.py "<url>" --prefix brainrot/sls/ --quality 1440 --keep
python fetch-upload.py "<url>" --cookies-from-browser chrome   # falls Bot-Check
```

- `--channel` nimmt den `r2_prefix` aus dem Kanalprofil; ohne Profil `--prefix`.
- Ohne `--out-dir`/`--keep` liegt die Datei nur temporär und wird nach dem
  Upload gelöscht. Der Upload **streamt** (kein RAM-Load bei großen Videos).
- Braucht `yt-dlp[default]`, `ffmpeg` und `boto3`; `--env-file r2.env` lädt
  fehlende `R2_*`-Variablen.

---

## 5. Python-Umgebung & Abhängigkeiten

Die Module sind reines Python (kein Paket, keine Installation nötig — sie laufen
aus dem Workspace).

**VPS: eigener venv.** Er liegt im Workspace-Root als `.venv/`
(`~/.openclaw/workspace-brainrothustler/.venv`) — **nicht** committen und beim
Update nicht überschreiben (wie `memory/`).

**Windows/MaxLaptop (verifiziert): kein venv** — die Module laufen gegen den
Host-Python (3.14, `C:\Program Files\Python314`), Pakete im User-sitepackages
`%APPDATA%\Python\Python314`.

Fremdpakete (alles andere ist stdlib):

| Modul | Braucht |
|---|---|
| `hosting` | `boto3`, `requests` |
| `yt_clips` | `numpy`, `Pillow`; `tesseract-ocr` (System) |
| `editor` | `ffmpeg` (System), `faster-whisper` (lokales Transkript) |
| `longterm_memory` | - (nur stdlib) |

VPS einrichten (genau einmal, aus dem Workspace-Root):

```bash
sudo apt install -y ffmpeg tesseract-ocr
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r modules/requirements.txt
```

**Aufrufweg für den Agenten ist der Wrapper `bin/cli`.** Er aktiviert die venv,
setzt `modules/` auf den `PYTHONPATH` und wechselt ins Workspace-Root — relative
Pfade zeigen damit auf `memory/`. Module werden nur so aufgerufen (siehe
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

Windows (kein venv), **aus `modules/`**: `python -m pytest tests` bzw.
`python -m hosting.cli …`.
`ffmpeg` kommt **vom System** (`apt install ffmpeg`): enthält libass für
`subtitles burn` und bekommt Sicherheitsupdates über apt. `imageio-ffmpeg`
bleibt nur Fallback für Hosts ohne System-Binary (Windows); `EDITOR_FFMPEG`
überschreibt beides.

**Tesseract** (OCR der Score-Einblendung) kommt ebenfalls vom System:
`apt install tesseract-ocr`. Das Paket bringt `eng` als Default mit, und für
Ziffern wie `9.10` braucht es kein weiteres Sprachpaket. Liegt das Binary nicht
im PATH, zeigt `TESSERACT_CMD` darauf. Ohne Tesseract läuft alles andere weiter,
nur `yt_clips ocr` fehlt (Fallback: `--engine rapidocr`, wenn
`rapidocr-onnxruntime` installiert ist).

---

## 6. Setup (Linux)

```bash
# 1) System-Pakete prüfen
ffmpeg -version
tesseract --version
#    Fehlt eines davon ("command not found"), dann:
#    sudo apt install -y ffmpeg tesseract-ocr

# 2) Repo ins OpenClaw-Verzeichnis klonen (siehe Verzeichniswechsel)
git clone <repo-url> ~/.openclaw/workspace-brainrothustler
cd ~/.openclaw/workspace-brainrothustler

# 3) Workspace-Dateien an ihren Platz
cp -a agent/. .
rm -rf agent
chmod +x bin/cli bin/channel    # beide Wrapper müssen ausführbar sein

# 4) venv anlegen + Modul-Abhängigkeiten (VPS)
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r modules/requirements.txt

# 5) Berechtigungen schreiben (setup/ liegt noch im Verzeichnis)
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

# 6) Prüfen und anwenden
openclaw config get agents.entries.brainrothustler.tools
openclaw exec-policy show --agent brainrothustler
openclaw approvals get --gateway
#    Allowlist muss BEIDE Wrapper enthalten (bin/cli und bin/channel)

# 7) Aufräumen: Repo-Rest weg, Workspace = nur die Agent-Dateien
#    (.venv/ bleibt stehen!)
rm -rf setup .git modules/requirements.txt README.md modules/requirements.txt modules/tests

openclaw gateway restart
```

Anschließend Telegram binden (eigener Bot-Account, Chat-ID = Owner).
Heartbeat: stündlich 09:00–22:00 (`lightContext`, isolierte Session).

---

## 7. Status

- Agent-Workspace-Struktur: steht (`agent/`).
- `setup/agent-config.json`: steht (Agent, Tools, `exec.mode: ask`, Heartbeat).
- `setup/exec-approvals.json`: steht — die Allowlist bindet **den Wrapper**
  (`~/.openclaw/workspace-brainrothustler/bin/cli`) mit einem `argPattern` über die
  Modul-CLIs. Der Interpreter steht **nicht** mehr drin (der Wrapper aktiviert die
  venv selbst) — damit ist der Wrapper das einzige erlaubte Einstiegstoken.
  **Partieller Patch** (nur `agents.brainrothustler`), vor dem Einspielen mergen.
- `agent/bin/cli`: Modul-Wrapper (venv aktivieren, `PYTHONPATH` auf `modules/`,
  `--channel` → `BRAINROT_CHANNEL`; startet `python3 -m` aus dem Workspace-Root).
  Muss im Deploy **ausführbar** sein (`chmod +x bin/cli`).
- **Video-Übergabe**: der Agent lädt nicht selbst. `request` schickt den Link an
  den Operator, er lädt (1080p mp4) und legt die Datei in den R2-Bucket;
  `fetch` holt sie von dort. Keine Cookies, kein PO-Token-Provider, kein yt-dlp.
- **Transkript**: entsteht lokal mit `faster-whisper` (`editor.cli subtitles
  transcribe`, CPU `int8`) — der Operator liefert nur das Video. Das Modell lädt
  einmalig in den Hugging-Face-Cache (`WHISPER_MODEL_DIR` verschiebt ihn).
- `agent/BOOTSTRAP.md` ist noch im Repo → ein Deploy startet das Onboarding
  erneut; vor dem ersten Deploy löschen oder bewusst behalten.

Verhalten und Grenzen des Agenten: `agent/AGENTS.md`.
