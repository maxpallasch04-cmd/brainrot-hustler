# Contentplan

Zentrale Warteschlange der geplanten Uploads. Wird bei jedem Heartbeat geprüft.
Takt und Ruhezeiten: siehe `AGENTS.md`.

## Einträge
- Jeder Eintrag nennt genau ein **Rezept** aus `recipes/`.
- Chronologisch nach Uploadzeit, frühester zuerst (oberster = nächster).
- Lebenslauf: `geplant` → `generiert` (Status setzen + `datei` eintragen)
  → `hochgeladen` (Eintrag entfernen, ins Langzeitgedächtnis).
- Nach dem Generieren bleibt der Eintrag **sichtbar** (Status `generiert` +
  Pfad) — so sieht der Agent, welches Video ansteht.
- Kein Archiv: hochgeladene Videos stehen im Langzeitgedächtnis.

## Format
Ein Block pro Upload (Beispiel, auskommentiert):
<!--
## 2026-10-09 18:00
- rezept: lifestory
- idee: <in einem Satz, was das Video ist>
- status: geplant
- datei:
- hochgeladen:
-->

## Offen

## 2026-10-10 18:00
- rezept: gencreep
- idee: Dashcam nachts auf nebliger Landstraße — am Rand steht reglos eine Gestalt, die beim Vorbeifahren kurz „mitgeht". Schnitt, bevor etwas passiert.
- status: generiert
- datei: out/gencreep-dashcam-2026-10-10.mp4
- hochgeladen:

## 2026-10-11 11:30
- rezept: foundsignal
- idee: Überwachungs-/Nachtsichtkamera bei Nacht an einem generischen Ort — erst nur Rauschen und Zeitstempel, dann steht eine Silhouette im Bild und ist beim nächsten Blick näher. Schnitt, bevor etwas passiert.
- status: geplant
- datei:
- hochgeladen:

## 2026-10-11 18:00
- rezept: gencreep
- idee: Handkamera im leeren Hausflur — die Tür am Ende steht einen Spalt offen, niemand da; Licht flackert, im Spiegel bewegt sich etwas.
- status: geplant
- datei:
- hochgeladen:

## 2026-10-12 11:30
- rezept: gencreep
- idee: Nachtsicht-Kamera in Wald/Garten — eine Silhouette zwischen den Bäumen; Kamera schwenkt weg und zurück, sie ist näher.
- status: geplant
- datei:
- hochgeladen:
