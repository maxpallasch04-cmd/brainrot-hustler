---
name: channel-setup
description: "Einen Kanal anlegen oder ändern: Werte im Chat erfragen, Profil in der DB speichern, Ergebnis prüfen."
---

# Kanal anlegen

Ein Kanal ist **eine Zeile in der `channel`-Tabelle**. Nichts davon gehört in
Markdown - `AGENTS.md` bleibt kanalunabhängig.

Der Nutzer gibt die Werte im Chat, du setzt sie um. Keine Werte erfinden.

## 1. Bestand prüfen

```
~/.openclaw/workspace-brainrothustler/bin/cli longterm_memory.cli channel-list
```

- **Leer** → neuer Kanal (weiter mit 2).
- **Kanal existiert** → nicht überschreiben. Fragen: *ändern* oder *zweiten Kanal
  anlegen*? Beim Ändern nur die genannten Felder übergeben - `channel-set` lässt
  alles andere stehen.

## 2. Werte erfragen

**Ein Block, alle Fragen auf einmal**, Defaults dazuschreiben - der Nutzer soll
nur abweichen müssen.

| Feld | Frage | Default |
| ---- | ----- | ------- |
| `id` | Kurz-ID des Kanals (a-z, 0-9, `-`, `_`, max. 32) | — (Pflicht) |
| `niche` | Nische in einem Satz | — (Pflicht) |
| `recipes` | welche Rezepte sind aktiv? | — (Pflicht, min. 1) |
| `art` | Standard-Videoart | `YT-Clip` |
| `open_target` | wie viele offene Einträge? | `2` |
| `lead_h` | Vorlauf vor Upload in Stunden | `4` |
| `quiet_start` / `quiet_end` | Ruhezeit von/bis (`HH:MM`) | `22:00` / `10:00` |
| `tz` | Zeitzone der Ruhezeit | `Europe/Berlin` |
| `format` | Zielformat | `9:16,1280` |
| `recipients` | wer bekommt Meldungen? (IDs) | — (leer = niemand) |
| `r2_prefix` | Ablage-Prefix im gemeinsamen Bucket | `brainrot/<id>/` |

**Rezepte:** vorher `ls recipes/` und nur existierende Namen anbieten. Ein Tippfehler
hier führt später dazu, dass `add-plan` jeden Eintrag ablehnt.

**Ruhezeiten** gelten in der Kanal-Zeitzone (`tz`), nicht in Serverzeit. Wrap über
Mitternacht ist erlaubt (`22:00` → `10:00`).

**Empfänger:** Telegram-IDs. Leer lassen ist okay, dann gibt es keine Meldungen -
das dem Nutzer aber sagen.

## 3. Anlegen

```
~/.openclaw/workspace-brainrothustler/bin/cli --channel <id> longterm_memory.cli channel-set \
    --niche "<niche>" --recipes <a>,<b> --art "YT-Clip" \
    --open-target 2 --lead-h 4 \
    --quiet-start 22:00 --quiet-end 10:00 --tz Europe/Berlin \
    --format "9:16,1280" --recipients <id1>,<id2>
```

Nur die Felder übergeben, die vom Default abweichen oder Pflicht sind.
`channel-set` ist idempotent: erneuter Aufruf aktualisiert, legt nicht doppelt an.

## 4. Prüfen (nicht weglassen)

```
bin/cli --channel <id> longterm_memory.cli channel-get     # Werte zurücklesen
bin/cli --channel <id> longterm_memory.cli task            # muss plan|idle liefern
```

- `channel-get` dem Nutzer zeigen (kurz, nicht als JSON-Block).
- `task` darf **nicht** mit `ChannelError` scheitern.
- Danach ist der Erststart fertig: `task` sagt `plan`, also fehlen die ersten
  Einträge - die legt die normale Pipeline an (`add-plan`), nicht dieser Skill.

## Regeln

- **Ein Kanal pro Aufruf.** Für einen zweiten Kanal den Skill erneut durchlaufen.
- ID nie raten und nie aus der Nische ableiten, ohne zu fragen.
- Keine Rezepte anlegen, nur zuordnen. Rezept-Inhalte gehören in `recipes/`.
- Kein `channel-set` auf Verdacht, um "schon mal was anzulegen".
