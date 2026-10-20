# Heartbeat

Kurzer, approximativer Check. Nichts fällig → nichts tun (kein Spam).

## Bei jedem Heartbeat

Ein Aufruf entscheidet alles (Schwellen kommen aus dem Kanalprofil):

```
~/.openclaw/workspace-brainrothustler/bin/cli --channel <id> longterm_memory.cli task
```

`action` sagt, was zu tun ist:

| `action` | Bedeutung | was du tust |
| -------- | --------- | ----------- |
| `upload` | `generated` und Uploadzeit vorbei | melden, dass hochgeladen werden soll (`videos`) |
| `pipeline` | ein `planned`-Eintrag ist fällig (Upload in < `lead_h`) | **Pipeline-Skill** mit `entry` ausführen |
| `plan` | `open < target` (= `open_target` aus dem Profil) | mit `add-plan` neue Einträge anlegen, bis `open` = `target` |
| `idle` | nichts fällig | nichts tun |

- Priorität ist genau diese Reihenfolge (zeitkritisch zuerst); was zusätzlich
  ansteht, steht in `also`.
- `entry` (bei `pipeline`) ist der komplette DB-Eintrag, `videos` (bei `upload`)
  die Liste der fälligen Videos.
- Nach dem Hochladen: `longterm_memory.cli upload <id>`.

## Kanäle

Bei mehreren Kanälen den Check **pro Kanal** ausführen:

```
... longterm_memory.cli channel-list        # aktive Kanäle
... --channel <id> longterm_memory.cli task
```
