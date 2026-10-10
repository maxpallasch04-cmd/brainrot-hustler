# Heartbeat

Kurzer, approximativer Check. Nichts fällig → nichts tun (kein Spam).
Regeln (≥3 offene Einträge, Ruhezeiten) stehen in `AGENTS.md`.

## Bei jedem Heartbeat
1. `contentplan.md` lesen.
2. **Genug geplant?** Weniger als 3 offene Einträge (`geplant` | `generiert`)
   → neu planen: Idee + **Rezept** (`recipes/<name>.md`) + Uploadzeit.
3. **Video fällig?** Nächster Eintrag mit Upload in **<4 h** und Status `geplant`
   → **Pipeline-Skill** ausführen.
4. **Upload verifizieren**: geplante Uploadzeit vorbei?
   → TikTok prüfen. Hochgeladen → ins Langzeitgedächtnis (`upload`) + Eintrag
   entfernen. Sonst → Nachricht, dass hochgeladen werden soll.
