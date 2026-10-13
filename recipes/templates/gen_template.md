---
name:                # Rezept-ID == Dateiname (lowercase, kein _), z.B. "gencreep"
art: Selbstgeneriert # Video_Art-Wert -> wählt den Generierungsskill (selfgen)
theme:               # Thema/Tag fürs Plan-Matching (z.B. "horror, gruselig")
model:               # provider/model-Override für video_generate (leer = OpenClaw-Standard, z.B. "kie/grok-imagine/text-to-video")
audio:               # true = Modell erzeugt Ton, false = stummer Clip
---

# <Rezeptname>

Beschreibe Randbedingungen und Stil (Cartoon, realistisch …), Vibe (fröhlich,
gruselig …), Ziel beim Zuschauer (Freude, Spannung …), Zielgruppe (jung, alt …)
sowie den inhaltlichen Themenbereich, Charakterarten, Konflikte … .
Die Beschreibung darf nicht zu konkret sein: jede Angabe als **generelle** Aussage,
damit sich möglichst wenig wiederholt.

## Auswahl
Woher kommt das Rohmaterial bzw. wie wird es ausgewählt (Kriterien, Ausschluss,
Zeitfenster/Sortierung).

## Background / Layout
Standardmäßig Vollbild, wahlweise anpassen.

## Musik
Standard: **vom Modell mitgeneriert** (`audio: true`); wahlweise Track aus dem Pool
(`assets/music/`, rotieren) — dann leise. `music_generate` nur auf Ansage.
Stil/Tempo, Lautstärke.

## Schnitt / Overlays
Schnitt-Tempo, Jumpcuts, Icons (x/y/Zeit), Effekte, Gesamtlänge.

## Ton / Titel / Beschreibung
Tonalität, Titel-Muster, Beschreibungs-Muster, Hashtags.

## Do / Don't
- Do: …
- Don't: …

## Beispiele
Referenzen (Links/Pfade) — als Vorlage für Werkzeug + Ton. (falls nötig)