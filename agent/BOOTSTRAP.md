# BOOTSTRAP - Erststart

Dieser Agent ist leer: **kein Kanal, keine Daten, kein Plan.**

## Aufgabe

Lege **einen Kanal nach den Angaben des Nutzers** an. Der Nutzer nennt die Werte
im Chat, du speicherst sie - **nichts erfinden, nichts raten**.

→ Ablauf, Fragen und Prüfungen: **`skills/channel-setup`**

Kurzfassung:

1. `bin/cli longterm_memory.cli channel-list` - ist wirklich keiner da?
2. Werte im Chat erfragen (ein Block, Defaults mitliefern).
3. `bin/cli --channel <id> longterm_memory.cli channel-set ...`
4. `channel-get` + `task` prüfen und das Ergebnis zeigen.

## Regeln

- Kanalprofile stehen **in der DB**, nicht in Markdown. Keine neue Datei anlegen.
- Fehlt eine Pflichtangabe (ID, Nische, Rezepte): **fragen**, nicht ausfüllen.
- Ohne Kanal startet kein kanalgebundenes Modul - der Erststart ist erst fertig,
  wenn `task` für den Kanal sauber antwortet.

Danach: Regeln in `AGENTS.md`, das Wie in `skills/`, Inhalte in `recipes/`.
