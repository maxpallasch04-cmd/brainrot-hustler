---
name: pipeline
description: "Führt die komplette Content-Pipeline aus: Plan-Eintrag → Rezept → Generierungsskill → Titel/Beschreibung → R2 → Telegram."
---

# Pipeline

Führt genau einen Eintrag aus der Datenbank von Anfang bis Ende aus. Der Eintrag
ist bereits präzise (Idee + Rezept) - hier wird nur ausgeführt, keine Idee erfunden.

**Kanal:** jeder Aufruf braucht `--channel <id>` (kommt im Heartbeat aus `task`).
Danach liegen alle Dateien unter `memory/<channel>/`.

## Ablauf

1. **Plan-Eintrag holen.** Die DB ist die Warteschlange, es gibt keine Datei:
   ```
   ~/.openclaw/workspace-brainrothustler/bin/channel <id> longterm_memory.cli nextdue
   ```
   Liefert `id`, `idea`, `recipe`, `plan_at`, `art` - oder `null` (nichts fällig).
   Im Heartbeat kommt der Eintrag direkt aus `task` (`action: pipeline`, Felder
   `channel` + `entry`) - dann `nextdue` nicht extra aufrufen.
2. **Rezept laden** (`read` `recipes/<recipe>.md`). Sein `art`-Feld wählt den
   Generierungsskill; seine Abschnitte (Auswahl, Background, Musik, Schnitt,
   Overlays) sind die Vorgabe.
3. **Generierungsskill passend zum `art` ausführen** - ein Skill pro Art:

   | `art`     | Skill    |
   | --------- | -------- |
   | `YT-Clip` | `ytclip` |

   Passt kein Skill zum `art` des Rezepts → **stoppen**, melden, nicht improvisieren.
   - Ergebnis: **eine `.mp4`** unter `memory/<channel>/videos/`.
   - Ein Skill darf **pausieren** (z. B. auf einen asynchronen Task warten oder
     eine Bestätigung brauchen) - dann hier später fortsetzen, nicht neu starten.
   - Liefert der Skill **Kontext** (Quelle, Zeitfenster, die Idee …), nimm ihn in
     die Folgeschritte mit.
4. **Titel + Beschreibung erzeugen** nach dem Ton-Abschnitt des Rezepts, gestützt
   auf den Kontext aus Schritt 3.
5. **Video hosten.**
   ```
   ~/.openclaw/workspace-brainrothustler/bin/channel <id> hosting.cli upload --file memory/<channel>/videos/<name>.mp4
   ```
   Die `url` aus dem JSON parsen. Der Bucket ist für alle Kanäle derselbe; getrennt
   wird nur über `r2_prefix` aus dem Profil. Innerhalb des Prefix bleibt nur das
   neueste Video (`R2_KEEP`) - der Link aus dem vorherigen Lauf ist danach weg.
6. **Eintrag erfassen + markieren.** Erst messen, dann in der DB als *generiert*
   eintragen - der Eintrag bleibt offen, bis er hochgeladen ist.
   ```
   ~/.openclaw/workspace-brainrothustler/bin/channel <id> editor.cli probe --in memory/<channel>/videos/<name>.mp4   # 9:16, Höhe = 1280, Länge
   ~/.openclaw/workspace-brainrothustler/bin/channel <id> longterm_memory.cli generated <id> \
       --title "<t>" --description "<d>" --file memory/<channel>/videos/<name>.mp4 --len-s <s> [--theme "<theme>"]
   ```
   Die `id` aus Schritt 1 verwenden - kein neuer Eintrag, kein Duplikat.
   Kontext aus Schritt 3 (z. B. Quelle/Zeitfenster) in `--description` mitführen.
7. **Melden.** Eine Telegram-Nachricht mit Video-Link, Titel, Beschreibung und
   geplanter Uploadzeit. Geht an die `recipients` des Kanalprofils.

## Hinweise

- **Ein Plan-Eintrag = ein Video.** Kein Lauf erzeugt mehrere Uploads auf einmal -
  sonst überschreiben sich die gehosteten Links (`R2_KEEP=1`).
- Der eigentliche Upload wird von der Upload-Erinnerung erledigt, nicht hier.
- Nach erfolgreichem Upload: `longterm_memory.cli upload <id>` (Status `uploaded`).
- Nichts in `modules/` ablegen - dort ist nur Code.
