---
name: recipebuilder
description: "Mit dem Nutzer ein Content-Rezept vorschlagen oder erarbeiten, in `recipes/` anlegen und in `AGENTS.md` aktivieren."
---

# Rezeptbauer

Macht aus einer Nische (Beschreibung + Beispiel + bevorzugte Art) ein
funktionierendes Rezept und verdrahtet es in den Agenten. Funktioniert überall:
aufgerufen aus `BOOTSTRAP.md` beim Erststart oder jederzeit, wenn der Nutzer ein
neues Rezept will — es holt sich, was es braucht.

## Templates
Der Skill ist **generierungs-unabhängig**: die artspezifischen Details stecken in
`recipes/templates/` — **ein Template pro Art** (`gen_template.md` → `Selbstgeneriert`,
`twitch_template.md` → `Twitch-Clip`, `yt_template.md` → `YT-Clip`, …). Ausgewählt wird über das `art`-Feld des
Templates. Neue Art = neues Template mit passendem `art` **und** ein Skill für
diese Art.

## Ablauf

1. **Inputs sammeln.** Nutze, was du schon hast; für den Rest den Nutzer fragen,
   eine Frage nach der anderen (konkrete Vorschläge, keine offenen Fragen):
   - Nischen-Beschreibung (worum es im Kanal geht, Zielgruppe, Sprache).
   - Ein konkretes Beispiel (ein Video/Thema, das passt).
   - Bevorzugte Art (`Selbstgeneriert` / `Twitch-Clip` / …).
   Bereits Beantwortetes überspringen (z. B. durch `BOOTSTRAP.md`).
2. **Bekannte Rezepte abgleichen.** Vorhandene `recipes/*.md` prüfen (ihr `art` +
   `theme`) und die Archetypen unten. Die passenden vorschlagen — je Name, eine
   Zeile — und den Nutzer bitten, eines zu wählen oder zu kombinieren.
   - `Selbstgeneriert`: `gencreep` (gruselige Stimmung). Weiterer Archetyp:
     `lifestory` (wahre Geschichte, Hoffnung) — noch nicht angelegt, über das
     Template bauen.
   - `Twitch-Clip`: noch kein aktives Beispiel — über das Template aufbauen.
   - `YT-Clip`: noch kein aktives Beispiel — über das Template aufbauen.
   - Nichts passt → zu Schritt 4.
3. **Bekanntes Rezept übernehmen** (falls gewählt): kopieren, Frontmatter anpassen
   (`name` = neue Datei-ID) und die Abschnitte an die Nische; dann zu Schritt 5.
4. **Von Grund auf bauen:** das zur gewählten Art passende Template aus
   `recipes/templates/` kopieren (auswählen über das `art`-Feld des Templates) und
   jeden Abschnitt füllen (Auswahl, Background/Layout, Musik, Schnitt/Overlays,
   Ton/Titel/Beschreibung, Do/Don't, Beispiele) aus den Inputs. Fehlendes beim Nutzer
   erfragen. `gencreep.md` als ausgearbeitetes Beispiel nutzen.
   Für ein Twitch-Rezept **Spiel oder Streamer** (Kategorie) und das
   Auswahlfenster/Sort fragen. Für ein YT-Rezept die **Quellen** und — aus dem
   Abschnitt `## Format` — **welche Boxen relevant sind** (das Vision-Modell
   erkennt Boxen, das Modell wählt danach aus).
5. **Frontmatter setzen + validieren:**
   - `name`: Datei-ID (= Dateiname, lowercase, kein `_`).
   - `art`: muss auf einen Skill zeigen — `Selbstgeneriert` → `selfgen`,
     `Twitch-Clip` → `cliptwitch`, `YT-Clip` → `ytclip` — und ein Template dieser Art unter
     `recipes/templates/` haben. Kein Skill/Template → **stoppen und melden**.
   - `theme`: kurzes Tag fürs Plan-Matching.
   - nur `Selbstgeneriert`: `model` (provider/model-Override, darf leer sein) und
     `audio: true|false`.
6. **Schreiben:** `recipes/<name>.md`.
7. **In `AGENTS.md` aktivieren:** den Namen bei **Aktive Rezepte** ergänzen
   (`_fülle aus_` ersetzen, sonst anhängen); **Bevorzugte Videoart** setzen und —
   falls noch leer — die Nischen-**Beschreibung** aus Schritt 1.
8. **Melden:** Rezeptname, Art, Theme und dass es jetzt aktiv ist.

## Hinweise

- Ein Rezept = ein konkreter Subtyp; kurz und spezifisch halten.
- Musik/Background sind **Pools**, nie Fix-Werte (rotieren).
- Nie eine Art ohne Skill erfinden (Schritt 5) — stattdessen melden.
- Neue Art: erst Template in `recipes/templates/` (passendes `art`), dann Skill.
- Die Nische wird nur *vorgeschlagen*, laut `AGENTS.md`.
- Standalone-Nutzung: gibt es noch keine Nische, *ist* das Rezept der Startpunkt —
  Inputs in Schritt 1 sammeln und die Nischen-Beschreibung in Schritt 7 füllen.
