# Heartbeat

Kurzer, approximativer Check. Nichts fällig → nichts tun (kein Spam).
Die Werte **N** (offene Einträge) und **T** (Vorlaufzeit) sowie die Ruhezeiten
stehen in `AGENTS.md` — hier nur der Ablauf.

## Bei jedem Heartbeat
1. `contentplan.md` lesen.
2. **Genug geplant?** Weniger als **N** offene Einträge (`geplant` | `generiert`)
   → neu planen: Idee + **Rezept** (`recipes/<name>.md`) + Uploadzeit.
   (N siehe `AGENTS.md`.)
3. **Video fällig?** Nächster Eintrag mit Upload in **< T h** und Status `geplant`
   (T siehe `AGENTS.md`) → **Pipeline-Skill** ausführen.
4. **Upload verifizieren**: geplante Uploadzeit vorbei?
   Optional `python3 -m monitoring.cli list-videos --max 5` prüfen (aus `modules/`).
   Hochgeladen → ins Langzeitgedächtnis (`upload`) + Eintrag entfernen. Sonst →
   Nachricht, dass hochgeladen werden soll.
