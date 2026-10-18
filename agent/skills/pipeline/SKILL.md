---
name: pipeline
description: "Führt die komplette Content-Pipeline aus: Plan-Eintrag → Rezept → Generierungsskill → Titel/Beschreibung → R2 → Telegram."
---

# Pipeline

Führt genau einen Eintrag aus `contentplan.md` von Anfang bis Ende aus. Der Eintrag
ist bereits präzise (Idee + Rezept) — hier wird nur ausgeführt, keine Idee erfunden.

## Ablauf

1. **Plan-Eintrag lesen** (`contentplan.md`). Er liefert die Idee, das Rezept
   (`recipes/<name>.md`) und die geplante Uploadzeit.
2. **Rezept laden** (`read` `recipes/<name>.md`). Sein `art`-Feld wählt den
   Generierungsskill; seine Abschnitte (Auswahl, Background, Musik, Schnitt,
   Overlays) sind die Vorgabe.
3. **Generierungsskill passend zum `art` ausführen** — ein Skill pro Art:

   | `art`     | Skill    |
   | --------- | -------- |
   | `YT-Clip` | `ytclip` |

   Passt kein Skill zum `art` des Rezepts → **stoppen**, melden, nicht improvisieren.
   - Ergebnis: **eine `.mp4`**.
   - Ein Skill darf **pausieren** (z. B. auf einen asynchronen Task warten oder
     eine Bestätigung brauchen) — dann hier später fortsetzen, nicht neu starten.
   - Liefert der Skill **Kontext** (Quelle, Zeitfenster, die Idee …), nimm ihn in
     die Folgeschritte mit.
4. **Titel + Beschreibung erzeugen** nach dem Ton-Abschnitt des Rezepts, gestützt
   auf  den Kontext aus Schritt 3.
5. **Video hosten.**
   ```
   ~/.openclaw/workspace-brainrothustler/bin/cli hosting.cli upload --file out.mp4      # R2; räumt alte Videos automatisch weg
   ```
   Die `url` aus dem JSON parsen. Nach dem Upload bleibt nur das neueste Video im
   Bucket (`R2_KEEP`) — der Link aus dem vorherigen Lauf ist danach weg.
6. **Eintrag erfassen + markieren.** Video ins Langzeitgedächtnis speichern. Dann
   den bestehenden Plan-Eintrag **in-place** bearbeiten: als *generiert* markieren
   und Speicherort + Name (Pfad) ergänzen. Nicht entfernen oder neu planen — der
   Eintrag existiert schon.
   ```
   ~/.openclaw/workspace-brainrothustler/bin/cli editor.cli probe --in out.mp4      # 9:16, Höhe ≥ 1280, Länge
   ~/.openclaw/workspace-brainrothustler/bin/cli longterm_memory.cli add-video --title "<t>" --art "YT-Clip" \
       --len-s <s> --description "<d>" --theme "<theme>" --recipe "<recipe>"
   ```
   Kontext aus Schritt 3 (z. B. Quelle/Zeitfenster) in `--description` mitführen.
   Die zurückgegebene `id` als `memory:` in den Plan-Eintrag schreiben — der
   Upload-Abgleich im Heartbeat braucht sie.
7. **Melden.** Eine Telegram-Nachricht mit Video-Link, Titel, Beschreibung und
   geplanter Uploadzeit. Geht an die registrierten Nutzer.

## Hinweise

- **Ein Plan-Eintrag = ein Video.** Kein Lauf erzeugt mehrere Uploads auf einmal —
  sonst überschreiben sich die gehosteten Links (`R2_KEEP=1`).
- Der eigentliche Upload wird von der Upload-Erinnerung erledigt, nicht hier.
