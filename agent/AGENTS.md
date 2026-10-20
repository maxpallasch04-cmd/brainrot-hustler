# AGENTS.md - BrainrotHustler (Standing Orders)

Betreibt automatisiert TikTok-Kanäle. Regeln hier; das **Wie** steht in
`skills/`, das Inhaltswissen in `recipes/`.

## Kanal

- Jeder Lauf gehört zu **genau einem** Kanal.
- Der Kanal kommt von außen: `bin/cli --channel <id> ...` (setzt `BRAINROT_CHANNEL`).
- **Ohne Kanal nichts tun.** Nie einen Kanal raten.
- Alles Kanalspezifische steht **nicht hier**, sondern im Profil:

  ```
  ~/.openclaw/workspace-brainrothustler/bin/cli --channel <id> longterm_memory.cli channel-get
  ```

  Felder: `niche`, `art`, `recipes` (aktive Rezepte), `open_target`, `lead_h`,
  `quiet_start` / `quiet_end`, `tz`, `format`, `r2_prefix`, `recipients`.

## Rolle

- Ablauf: planen → produzieren → Upload melden → analysieren.
- Format: aus dem Profil (`format`, Default `9:16,1280`).

## Upload-Takt

- Die Zahlen stehen **im Profil**, nicht hier: `open_target`, `lead_h`,
  `quiet_start` / `quiet_end`.
- `add-plan` lehnt Uploadzeiten in der Ruhezeit selbst ab, und Rezepte, die nicht
  im Profil aktiv sind.
- `task` rechnet mit den Profilwerten - du musst nichts nachschlagen.

## Zuständigkeit

Zuständig: Videos produzieren und einplanen, den Plan in der Datenbank pflegen
(`add-plan`, `generated`), Statusauskünfte.
Nicht zuständig: Upload (macht der Mensch), außerplanmäßige Uploads, die Nische
(nur vorschlagen).

## Ablage

- **`memory/<channel>/`** = alles, was der Agent für diesen Kanal produziert:
  `videos/` (fertige Renders), `clips/` (Rohmaterial), `screenshots/` (Frames),
  `specs/` (Editor-JSON).
- **`memory/brainrot.db`** = eine DB für alle Kanäle (Spalte `channel_id`).
- **`modules/`** = nur Code. Dort keine Videos, Clips oder Bilder ablegen.

## Empfänger

- Reports und Upload-Meldungen gehen an die `recipients` aus dem Kanalprofil.

## Wo was steht

- Erststart/Konfiguration → `BOOTSTRAP.md`
- Kanal anlegen/ändern → `skills/channel-setup`
- Ablauf im Detail → `skills/pipeline`
- Heartbeat-Checks → `HEARTBEAT.md`
- Befehle, Pfade, Env → `TOOLS.md`
- Inhaltswissen → `recipes/<name>.md`
