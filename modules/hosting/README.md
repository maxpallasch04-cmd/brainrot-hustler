# hosting

Gib ihm eine Datei → bekomme eine öffentliche URL; oder gib ihm einen Link →
bekomme eine Datei. Anonym, keine Zugangsdaten.

- **catbox** — permanente Links, max. **200 MB** (Standard).
- **litterbox** — selbst-ablaufende Links (`1h` / `12h` / `24h` / `72h`), max.
  **1 GB** (`expires` übergeben).

## CLI

```
python3 -m hosting.cli upload --file out.mp4
python3 -m hosting.cli upload --file out.mp4 --expires 24h      # litterbox
echo "hi" | python3 -m hosting.cli upload --file - --filename hello.txt
python3 -m hosting.cli download --url https://files.catbox.moe/abc.mp4 --out clips/abc.mp4
```

Upload-Ausgabe-JSON: `url`, `host`, `expires`, `filename`, `bytes`.
Download-Ausgabe-JSON: `path`, `bytes`, `filename`, `url`, `content_type`.

## Python-API

```python
from hosting import upload, upload_file, upload_bytes, download

url = upload_file("out.mp4")                    # -> "https://files.catbox.moe/....mp4"
url = upload_file("out.mp4", expires="24h")     # -> litterbox, selbst-ablaufend
url = upload_bytes(b"...", "clip.mp4")          # rohe Bytes

info = download("https://files.catbox.moe/abc.mp4", dest="clips/abc.mp4")
# -> {"path": ..., "bytes": ..., "filename": ..., "url": ..., "content_type": ...}
```

Alle geben den URL-String zurück. Fehler werfen `hosting.UploadError` (fehlende
Datei, Größenlimit, ungültiges `expires` oder Host-Fehler). `download` wirft
`hosting.DownloadError` (schlechte URL, HTTP-Fehler oder über `max_bytes`).
