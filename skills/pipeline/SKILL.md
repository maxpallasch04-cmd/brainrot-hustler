---
name: pipeline
description: "Führt die komplette Content-Pipeline aus: Plan-Eintrag → Rezept → Generierungsskill → Titel/Beschreibung → catbox → Telegram."
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
3. **Generierungsskill passend zum `art` des Rezepts ausführen** — ein Skill pro
   Art. `Twitch-Clip` → `cliptwitch`, `Selbstgeneriert` → `selfgen`.
   Passt kein Skill zum `art` des Rezepts → **stoppen**, melden, nicht improvisieren.
   Ergebnis: eine `.mp4` (selbstgenerierte Videos kommen asynchron — siehe `selfgen`).
4. **Titel + Beschreibung erzeugen** nach dem Ton-Abschnitt des Rezepts, gestützt
   auf das Kanalwissen im Langzeitgedächtnis.
5. **Video hosten.**
   ```
   python3 -m hosting.cli upload --file out.mp4      # catbox, permanent, ≤200 MB
   ```
   Die `url` aus dem JSON parsen.
6. **Eintrag erfassen + markieren.** Video ins Langzeitgedächtnis speichern. Dann den
   bestehenden Plan-Eintrag **in-place** bearbeiten: nur als *generiert* markieren
   und Speicherort + Name (Pfad) ergänzen. Nicht entfernen oder neu planen — der
   Eintrag existiert schon.
   ```
   python3 -m video_generation.cli probe --in out.mp4      # Länge für --len-s
   python3 -m longterm_memory.cli add-video --title "<t>" --art "Selbstgeneriert" \
       --len-s <s> --description "<d>" --theme "<theme>" --recipe "<recipe>"
   ```
7. **Melden.** Eine Telegram-Nachricht mit catbox-Link, Titel, Beschreibung und
   geplanter Uploadzeit. Geht an die registrierten Nutzer.

## Hinweise

- Der Plan-Eintrag bleibt; er wird nur in-place bearbeitet (generiert + Pfad).
- Der eigentliche Upload wird von der Upload-Erinnerung erledigt, nicht hier.
