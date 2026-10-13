---
name: gencreep
art: Selbstgeneriert
theme: horror, gruselig, creepypasta
model: kie/grok-imagine/text-to-video
duration_s: 6
resolution: 480P   
audio: true          
---

# gencreep

Ziel: eine besonders furchteinflößende Atmosphäre. Es muss und soll nicht direkt
etwas Verstörendes oder Brutales zu sehen sein — allein das Andeuten, zusammen
mit der gruseligen Atmosphäre, erzeugt Nervenkitzel und hält den Zuschauer bis
zum angedeuteten „Ereignis" dabei.

## Auswahl
Rohmaterial selbstgeneriert (`video_generate`, ein Clip 4/6/8 s): bewusst schlechte
Qualität im Retro-Stil, Found-Footage-Look (Handkamera, VHS/Dashcam, Nachtsicht),
kein On-Screen-Text, keine Logos.
- Motiv: ein Ort/Detail, an dem etwas nicht stimmt (Wald, Flur, Zimmer) — ein
  angedeutetes „Ereignis", kein Schock.
- Ausschluss: Gewalt/Verletzung, deutliche Monster, Splatter.

## Background / Layout
9:16, Vollbild, gerendertes Video.

## Musik
Vorgegebener Track aus dem Musik-Pool (`assets/music/` — siehe Asset-Liste unten),
kein Selbstgenerieren. Dunkel/creepy.
- **Leise untermischen:** das Modell liefert eigenen Ton (`audio: true`) → Track
  nicht die Modell-Atmosphäre übertönen.
- Track pro Video rotieren.
- **Tracks nicht an unterschiedlichen Stellen starten** — immer ab demselben
  Punkt (z. B. Anfang), nicht je Video ein anderer Offset.

## Schnitt / Overlays
- Gesamtlänge: ein Clip **6 s** (`durationSeconds` 6, **480P** — hält die Datei unter dem 16-MB-Download-Limit des Providers); länger nur
  über `concat`.
- Schnitt: keine hektischen Jumpcuts — das Grauen liegt in der Ruhe.
- **Rausch-Filter aktiv:** VHS-Look übers ganze Bild — im Render-Recipe
  `"noise": {"amount": 0.08, "mode": "vhs"}` (top-level).
- Overlay: ein Icon aus der Asset-Liste (unten), mittig unten, erste 2 s.

## Ton / Titel / Beschreibung
- Grundton: unheimlich statt laut — **Untertreibung**. Das Normale/Beiläufige
  kippt ins Falsche; das Grauen steckt im Detail, nicht im Schock.
- Wirkung: beklemmend, unausweichlich (das Ereignis ist schon geschehen, kein
  Entkommen), aus der Beobachter-/Found-Footage-Perspektive.
- Titel: andeutend, lowercase, 2. Person, keine Auflösung
  (z. B. „hast du das auch gesehen?").
- Beschreibung: 1 knappe Zeile + 3–5 Hashtags (#creepy #fyp #horror #creepypasta).

## Do / Don't
- Do: ein exaktes „Ereignis" andeuten (Monster im Wald, Überfall, Zugunglück);
  Atmosphäre düster; bewusst offen; die Situation wirkt real.
- Don't: keine Gewalt, Verletzung oder zu furchteinflößende Monster zeigen.

## Beispiele
**Idee (Vorlage):** Dashcam-/Handkamera-Aufnahme bei Nacht auf leerer Landstraße,
Nebel. Am Rand steht reglos eine Gestalt, die beim Vorbeifahren kurz „mitgeht".
Bild zittert, rauscht — Schnitt, bevor etwas passiert. Offenes Ende, keine Auflösung.

**Prompt (ein Clip, 9:16, kein Text/Gore):** Found-footage dashcam POV, night,
empty foggy rural road; a motionless human silhouette standing at the roadside,
facing the road; as the camera passes it briefly appears to move with the car;
handheld shake, heavy VHS grain, low light, cold desaturated palette, unsettling,
subtle, realistic; no on-screen text, no logos.

## Asset-Liste
Wird laufend ergänzt (ähnliche Icons + Musik).
- Musik: `assets/music/Patience & Prudence - Tonight You Belong To Me (Official Audio).mp3` — **passt nicht** (fröhlich); creepy Tracks fehlen noch.
- Icon: `assets/icons/youdontdaretofollow.png`
