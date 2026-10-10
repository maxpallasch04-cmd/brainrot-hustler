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
