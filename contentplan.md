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

## 2026-10-16
Ziel: 4 Uploads/Tag (Europe/Berlin), Ruhezeit 21:00–10:00.
Slots heute: 11:00 · 14:00 · 17:00 · 20:00 (Uhrzeit = geplante Uploadzeit).

- rezept: ytsls-besttrick
- idee: SLS Best-Trick aus vollem Wettkampf (Trick + Reaktion + Score ≥ 8)
- upload: 2026-10-16 11:00 Europe/Berlin
- status: geplant
- datei:

- rezept: ytsls-besttrick
- idee: SLS Best-Trick aus vollem Wettkampf (Trick + Reaktion + Score ≥ 8)
- upload: 2026-10-16 14:00 Europe/Berlin
- status: geplant
- datei:

- rezept: ytsls-besttrick
- idee: SLS Best-Trick aus vollem Wettkampf (Trick + Reaktion + Score ≥ 8)
- upload: 2026-10-16 17:00 Europe/Berlin
- status: geplant
- datei:

- rezept: ytsls-besttrick
- idee: SLS Best-Trick aus vollem Wettkampf (Trick + Reaktion + Score ≥ 8)
- upload: 2026-10-16 20:00 Europe/Berlin
- status: geplant
- datei:

## 2026-10-17
Slots: 11:00 · 14:00 · 17:00 · 20:00 (Europe/Berlin).

- rezept: ytsls-besttrick
- idee: SLS Best-Trick aus vollem Wettkampf (Trick + Reaktion + Score ≥ 8)
- upload: 2026-10-17 11:00 Europe/Berlin
- status: geplant
- datei:

- rezept: ytsls-besttrick
- idee: SLS Best-Trick aus vollem Wettkampf (Trick + Reaktion + Score ≥ 8)
- upload: 2026-10-17 14:00 Europe/Berlin
- status: geplant
- datei:

- rezept: ytsls-besttrick
- idee: SLS Best-Trick aus vollem Wettkampf (Trick + Reaktion + Score ≥ 8)
- upload: 2026-10-17 17:00 Europe/Berlin
- status: geplant
- datei:

- rezept: ytsls-besttrick
- idee: SLS Best-Trick aus vollem Wettkampf (Trick + Reaktion + Score ≥ 8)
- upload: 2026-10-17 20:00 Europe/Berlin
- status: geplant
- datei:
