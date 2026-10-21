# Heartbeat

Kurzer, approximativer Check. Nichts fällig → nichts tun (kein Spam).

## Bei jedem Heartbeat

Ein Aufruf entscheidet alles - **kanal-frei**, über alle aktiven Kanäle:

```
~/.openclaw/workspace-brainrothustler/bin/cli longterm_memory.cli task
```

`action` sagt, was zu tun ist, `channel` sagt, für wen:

| `action` | Bedeutung | was du tust |
| -------- | --------- | ----------- |
| `upload` | `generated` und Uploadzeit vorbei | melden, dass für `channel` hochgeladen werden soll (`videos`) |
| `pipeline` | ein `planned`-Eintrag ist fällig (Upload in < `lead_h`) | **Pipeline-Skill** für `channel` mit `entry` ausführen |
| `plan` | `open < target` | mit `add-plan` für `channel` neue Einträge anlegen, bis `open` = `target` |
| `idle` | nichts fällig | nichts tun |

- Priorität global: `upload` → `pipeline` → `plan` → `idle`. Bei mehreren Kanälen
  mit derselben Aktion gewinnt der dringendste (früheste Uploadzeit, größtes Defizit).
- `video` sagt, um welches Video es geht: `id`, `label`, `title`, `idea`,
  `recipe`, `file`, `plan_at_local`, `status`. Bei `pipeline` der fällige
  Eintrag, bei `upload` das dringendste der Liste, bei `plan`/`idle` fehlt es.
- `channels` listet den Stand aller aktiven Kanäle - dort siehst du, was als
  Nächstes dran ist.
- `entry` (bei `pipeline`) ist der komplette DB-Eintrag, `videos` (bei `upload`)
  die Liste der fälligen Videos.
- Nach dem Hochladen: `bin/channel <channel> longterm_memory.cli upload <id>`.

## Kein Kanal angelegt

`task` endet dann mit einer Fehlermeldung (kein `idle`): erst
`channel-set` ausführen → `skills/channel-setup`.
