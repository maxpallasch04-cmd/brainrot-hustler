# Contentplan

Zentrale Warteschlange der geplanten Uploads. Wird bei jedem Heartbeat geprüft.
Takt, Vorlaufzeit und Ruhezeiten: siehe `AGENTS.md`.

## Einträge
- Jeder Eintrag nennt genau ein **Rezept** aus `recipes/` (`rezept`-Feld).
- Chronologisch nach Uploadzeit, frühester zuerst (oberster = nächster).
- Lebenslauf: `geplant` → `generiert` (Status setzen + `datei` eintragen)
  → `hochgeladen` (Eintrag entfernen, ins Langzeitgedächtnis).
- Nach dem Generieren bleibt der Eintrag **sichtbar** (Status `generiert` +
  Pfad) — so sieht der Agent, welches Video ansteht.
- Kein Archiv: hochgeladene Videos stehen im Langzeitgedächtnis.

## Format
Ein Block pro Upload. Felder:
- `rezept` — Rezept-ID (`recipes/<name>.md`).
- `idee` — in einem Satz, was das Video ist.
- `status` — `geplant` | `generiert`.
- `datei` — Pfad der gerenderten `.mp4` (leer bis generiert).

```
## 2026-10-09 18:00
- rezept: ytsls-besttrick
- idee: Best-Trick Kickflip Backside Tailslide, Score 9.10
- status: geplant
- datei:
```

## Offen
_Noch keine Einträge._
