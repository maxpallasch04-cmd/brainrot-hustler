# BrainrotHustler

Ein Agent, der automatisiert einen TikTok-Kanal betreibt: planen → produzieren →
Upload melden → analysieren. **Den Upload macht der Mensch.**

## Struktur
- `AGENTS.md` — Standing Orders (Nische, Takt, Zuständigkeit).
- `BOOTSTRAP.md` — einmaliges Onboarding (danach löschen).
- `SOUL.md` / `IDENTITY.md` / `USER.md` — Haltung, Identität, Nutzer.
- `HEARTBEAT.md` — periodischer Check.
- `contentplan.md` — Warteschlange der geplanten Uploads.
- `skills/` — das **Wie** (Abläufe): `pipeline`, `selfgen`, `ytclip`,
  `cliptwitch`, `recipebuilder`, `monitorreport`.
- `recipes/` — das **Inhaltswissen** je Subtyp; Vorlagen in `recipes/templates/`.
- `modules/` — Python-CLIs (`yt_clips`, `twitch_clips`, `video_generation`,
  `subtitles`, `hosting`, `longterm_memory`, `monitoring`) + `modules/tests/`.
- `assets/` — Icon-/Musik-Pool.
- `TOOLS.md` — Befehle, Pfade, Env.

## Ablauf
- Der Agent folgt `AGENTS.md` + `HEARTBEAT.md`; die Abläufe stehen in `skills/`,
  das Inhaltswissen in `recipes/`.
- Modul-Befehle laufen aus `modules/`: `python3 -m <modul>.cli …`.
