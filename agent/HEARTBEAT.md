# Heartbeat

Kurzer, approximativer Check. Nichts fällig → nichts tun (kein Spam).
Die Werte **N** (offene Einträge) und **T** (Vorlaufzeit) sowie die Ruhezeiten
stehen in `AGENTS.md` — hier nur der Ablauf.

## Bei jedem Heartbeat
1. `contentplan.md` lesen.
2. **Genug geplant?** Weniger als **2** offene Einträge (`geplant` | `generiert`)
   → neu planen: Idee + **Rezept** (`recipes/<name>.md`) + Uploadzeit.
3. **Video fällig?** Nächster Eintrag mit Upload in **< 4 h** und Status `geplant`→ **Pipeline-Skill** ausführen.
4. **Upload verifizieren**: geplante Uploadzeit vorbei?
   Hochgeladen → `longterm_memory.cli upload <memory-id>` + Eintrag entfernen.
   Sonst → Nachricht, dass hochgeladen werden soll.
