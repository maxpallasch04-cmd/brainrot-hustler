# hosting

> **Aufruf:** `~/.openclaw/workspace-brainrothustler/bin/cli <modul>.cli <args>`
> (Workspace-Wrapper, siehe `TOOLS.md`) — aus jedem cwd, venv wird automatisch aktiviert.

Gib ihm eine Datei → bekomme eine öffentliche URL; oder gib ihm einen Link →
bekomme eine Datei.

Uploads gehen in den eigenen **Cloudflare-R2-Bucket** (S3-kompatibel): läuft von
Rechenzentrums-IPs, kommerziell erlaubt, 10 GB/Monat gratis, Egress frei.
Zugänge aus dem **OpenClaw-Team-Store** (Kind `env`, siehe `TOOLS.md`). Kein
anonymer Host, kein Fallback.

Nach jedem Upload wird **aufgeräumt**: nur die neuesten `R2_KEEP` Objekte bleiben
(Default 1), die Gesamtgröße bleibt unter `R2_QUOTA_GB` (Default 10). Gelöscht
wird nur **innerhalb des eigenen Prefix** - Kanäle löschen sich nicht gegenseitig.
Löschen ist gratis und läuft in einem einzigen Bulk-Request.

## Kanäle: ein Bucket, ein Prefix pro Kanal

Alle Kanäle teilen sich Bucket und Zugänge (keine zweite `.env`, kein zweites
Token). Getrennt wird ausschließlich über den Key-Prefix:

- `BRAINROT_CHANNEL` gesetzt (macht der Wrapper via `--channel`) → Prefix aus dem
  Kanalprofil (`r2_prefix`, Default `brainrot/<id>/`).
- `R2_PREFIX` gesetzt → gewinnt immer (manueller Override).
- Nichts gesetzt → alter Default `videos/`.

Dadurch gilt `R2_KEEP` **pro Kanal**: ein Upload von Kanal A löscht nicht das
Video von Kanal B.

## CLI

```
~/.openclaw/workspace-brainrothustler/bin/cli hosting.cli upload --file out.mp4                     # hochladen + aufräumen
~/.openclaw/workspace-brainrothustler/bin/cli hosting.cli upload --file out.mp4 --no-prune          # ohne Aufräumen
~/.openclaw/workspace-brainrothustler/bin/cli hosting.cli upload --file out.mp4 --key videos/x.mp4  # eigener Key
echo "hi" | ~/.openclaw/workspace-brainrothustler/bin/cli hosting.cli upload --file - --filename hello.txt
~/.openclaw/workspace-brainrothustler/bin/cli hosting.cli usage                                     # Objekte + freier Platz
~/.openclaw/workspace-brainrothustler/bin/cli hosting.cli prune                                     # manuell aufräumen
~/.openclaw/workspace-brainrothustler/bin/cli hosting.cli download --url <link> --out clips/x.mp4   # Direktlink → Datei
```

Upload-Ausgabe-JSON: `url`, `host`, `bucket`, `key`, `filename`, `bytes`, `pruned`
(`deleted` / `kept` / `bytes` / `quota_bytes`). Steht `prune_error` drin, war der
Upload ok — nur das Aufräumen scheiterte.
Usage-Ausgabe-JSON: `objects`, `bytes`, `quota_bytes`, `free_bytes`, `keys`.
Download-Ausgabe-JSON: `path`, `bytes`, `filename`, `url`, `content_type`.

## Konfiguration (OpenClaw-Team-Store)

Die Werte liegen im OpenClaw-Team-Store (Kind `env`) und werden automatisch als
Umgebungsvariablen injiziert; `hosting` liest sie aus `os.environ`. Kein `.env`,
kein Fallback-Loader.

Pflicht: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`,
`R2_PUBLIC_BASE_URL` (r2.dev-Subdomain oder eigene Domain).
Optional: `R2_ENDPOINT`, `R2_PREFIX` (Default `videos/`, überschreibt den
Profil-Prefix), `R2_KEEP` (Default 1), `R2_QUOTA_GB` (Default 10).
Braucht `boto3` (`pip install -r modules/requirements.txt`). Fehler werfen
`hosting.R2Error` (fehlende Config, boto3 fehlt, Bucket-Fehler).

## Python-API

```python
from hosting import upload_file, prune, usage, r2

url = upload_file("out.mp4")            # -> "https://pub-....r2.dev/videos/..."
key = r2.object_key("clip.mp4")         # Key bauen (videos/YYYY-MM-DD/...)
prune(protect={key})                    # aufräumen (nach dem Upload)
usage()                                 # {"objects": ..., "bytes": ..., "free_bytes": ...}
```

`upload_file`/`upload_bytes`/`upload` geben den URL-String zurück und räumen
**nicht** selbst auf — das macht `prune` (die CLI ruft es automatisch nach dem
Upload). `r2.upload*` wirft `hosting.R2Error`. `download` wirft
`hosting.DownloadError` (schlechte URL, HTTP-Fehler oder über `max_bytes`).
