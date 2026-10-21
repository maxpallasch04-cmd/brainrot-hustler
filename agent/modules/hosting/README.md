# hosting

Dateien raus und rein über **Cloudflare R2**: `upload` gibt eine öffentliche URL
zurück, `download` holt eine Datei wieder. Alle Kanäle teilen sich einen Bucket;
getrennt wird nur über den Prefix aus dem Kanalprofil.

`hosting` kennt keine Kanäle im Code - es liest den Prefix, der zum Aufruf gehört.
Deshalb läuft jeder Upload über `bin/channel`.

## CLI

```
bin/channel <id> hosting.cli upload   --file memory/<channel>/videos/x.mp4
bin/channel <id> hosting.cli upload   --file x.mp4 --no-prune
bin/channel <id> hosting.cli upload   --file x.mp4 --key videos/eigener-name.mp4
cat x.txt | bin/channel <id> hosting.cli upload --file - --filename x.txt
bin/channel <id> hosting.cli download --url <link> --out memory/<channel>/clips/x.mp4
bin/channel <id> hosting.cli usage
bin/channel <id> hosting.cli prune    [--keep 3] [--quota-gb 5]
```

| Befehl | Ausgabe (JSON) |
| --- | --- |
| `upload` | `url`, `host`, `bucket`, `key`, `filename`, `bytes`, `pruned` |
| `download` | `path`, `bytes`, `filename`, `url`, `content_type` |
| `usage` | `objects`, `bytes`, `quota_bytes`, `free_bytes`, `keys` |
| `prune` | `deleted`, `kept`, `bytes`, `quota_bytes` |

Steht in `upload` ein `prune_error`, war der Upload erfolgreich - nur das
Aufräumen ist gescheitert.

## Aufräumen

Nach jedem Upload wird innerhalb des Prefix aufgeräumt: standardmäßig bleibt
**nur das neueste Objekt**. Der Link aus dem vorherigen Lauf ist danach tot -
wer ihn noch braucht, muss den Upload mit `--no-prune` machen.

`prune` arbeitet ausschließlich im Prefix des Kanals, löscht also nie die Videos
eines anderen Kanals. `--keep` und `--quota-gb` überschreiben die Defaults für
einen Lauf; die dauerhaften Werte stehen in der Projekt-README.

## Fehler

`R2Error` bei fehlender Konfiguration, fehlendem `boto3` oder Bucket-Fehlern;
`DownloadError` bei kaputter URL, HTTP-Fehler oder zu großer Datei. Ohne Kanal
und ohne expliziten Prefix bricht `upload` ab, statt in einen gemeinsamen
Prefix zu schreiben.
