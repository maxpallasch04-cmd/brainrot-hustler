# Heartbeat

Kurzer, approximativer Check. Nichts fällig → nichts tun (kein Spam).

## Bei jedem Heartbeat

Ein Aufruf entscheidet alles:

```
~/.openclaw/workspace-brainrothustler/bin/cli longterm_memory.cli task
```

`action` sagt, was zu tun ist:

| `action` | Bedeutung | was du tust |
| -------- | --------- | ----------- |
| `upload` | `generated` und Uploadzeit vorbei | melden, dass hochgeladen werden soll (`videos`) |
| `pipeline` | ein `planned`-Eintrag ist fällig (Upload in < 4 h) | **Pipeline-Skill** mit `entry` ausführen |
| `plan` | `open < target` (Default 2) | mit `add-plan` neue Einträge anlegen, bis `open` = `target` |
| `idle` | nichts fällig | nichts tun |

- Priorität ist genau diese Reihenfolge (zeitkritisch zuerst); was zusätzlich
  ansteht, steht in `also`.
- `entry` (bei `pipeline`) ist der komplette DB-Eintrag, `videos` (bei `upload`)
  die Liste der fälligen Videos.

