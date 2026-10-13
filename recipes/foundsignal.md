---
name: foundsignal
art: Selbstgeneriert
theme: horror, nachtsicht, ueberwachung
model: kie/grok-imagine/text-to-video
duration_s: 6
resolution: 480P
audio: true
---

# foundsignal

Ziel: die beklemmende Ruhe von Überwachungs-/Nachtsichtaufnahmen — ein Ort bei
Nacht, an dem etwas nicht stimmt. Es passiert nie etwas Sichtbares; das Grauen
entsteht allein aus der Differenz zwischen zwei Einstellungen: erst ist niemand
da, dann steht eine Gestalt, und beim nächsten Blick ist sie näher. Andeutung
statt Schock. Zielgruppe: deutschsprachige TikTok-Nutzer, Horror/Creepypasta.

## Auswahl
Rohmaterial selbstgeneriert (`video_generate`, ein Clip 4/6/8 s): bewusst
schlechte Qualität im Überwachungs-/Nachtsicht-Look (monochrom, VHS-Rauschen,
Zeitstempel-Ecke, leichte Fisheye), kein On-Screen-Text außer dem Cam-Zeitstempel,
keine Logos.
- Location: **generisch** — ein Pool (Waldrand, Garten, Hof, Feldweg, Parkplatz,
  Hinterhof …), nie ein Fix-Ort; pro Video rotieren.
- Kamera-Charakter: **Pool** — statische Überwachungskamera / schwenkende PTZ /
  Wildkamera mit Bewegungsauslöser (kurze, ruckelige Clips).
- Motiv: eine bewegungslose Silhouette/Gestalt, die zwischen den Einstellungen
  näher kommt — kein Schock, keine Auflösung.
- Ausschluss: Gewalt/Verletzung, deutliche Monster, Splatter.

## Background / Layout
9:16, Vollbild, gerendertes Video.

## Musik
Standard: **vom Modell mitgeneriert** (`audio: true`) — das leise Knacken/Rauschen
der Aufnahme ist Teil der Atmosphäre. Track aus dem Pool nur leise untermischen
(rotieren); der Pool enthält aktuell **keinen passenden creepy Track** (Lücke).
`music_generate` nur auf Ansage.

## Schnitt / Overlays
- Gesamtlänge: ein Clip **6 s** (`durationSeconds` 6, **480P** — hält die Datei
  unter dem 16-MB-Download-Limit des Providers); länger nur über `concat`.
- Schnitt: **keine hektischen Jumpcuts** — das Grauen liegt in der Ruhe und im
  Zeitsprung zwischen den Einstellungen (Bild rauscht/blinkt, nächster Frame: näher).
- **Rausch-Filter aktiv:** im Render-Recipe `"noise": {"amount": 0.08, "mode": "vhs"}`
  (top-level).
- Overlay: ein Icon aus der Asset-Liste (unten), mittig unten, erste 2 s.

## Ton / Titel / Beschreibung
- Grundton: unheimlich statt laut — **Untertreibung**. Das Beiläufige kippt ins
  Falsche; das Grauen steckt im Detail, nicht im Schock.
- Wirkung: beklemmend, unausweichlich (das Ereignis ist schon geschehen, kein
  Entkommen), aus der Kamera-/Found-Footage-Perspektive.
- Titel: andeutend, lowercase, 2. Person, keine Auflösung
  (z. B. „sie steht wieder da").
- Beschreibung: 1 knappe Zeile + 3–5 Hashtags (#creepy #fyp #horror #creepypasta).

## Do / Don't
- Do: genau ein angedeutetes „Ereignis" (Gestalt kommt näher); Atmosphäre düster,
  bewusst offen; die Situation wirkt real.
- Don't: keine Gewalt, Verletzung oder zu furchteinflößende Monster zeigen.

## Beispiele
**Idee (Vorlage):** Nachtsicht-/Überwachungsaufnahme bei Nacht an einem generischen
Ort (Waldrand/Hof). Erst ist nichts zu sehen, nur Rauschen und ein Zeitstempel;
dann steht eine Silhouette im Bild, und beim nächsten Blick ist sie näher.
Bild rauscht — Schnitt, bevor etwas passiert. Offenes Ende.

**Prompt (ein Clip, 9:16, kein Text/Gore):** Night-vision surveillance-camera POV,
outdoor at night, generic dark location (forest edge / yard), heavy monochrome
grain, timestamp corner, slight fisheye; a motionless human silhouette appears at
the edge of the frame and is closer in the next cut; unsettling, subtle, realistic;
no on-screen text except the camera timestamp, no logos.

## Asset-Liste
Wird laufend ergänzt.
- Musik: `assets/music/Patience & Prudence - Tonight You Belong To Me (Official Audio).mp3` — **passt nicht** (fröhlich); creepy Tracks fehlen noch.
- Icon: `assets/icons/youdontdaretofollow.png`
