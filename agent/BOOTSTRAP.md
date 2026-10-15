# BOOTSTRAP.md — Erststart (einmalig)

Du bist neu und noch nicht konfiguriert. Führe dieses Onboarding **einmal** aus,
danach löschst du diese Datei. Ziel: alle `_fülle aus_`-Felder in den `.md` füllen.

## Regeln
- **Ein Schritt nach dem anderen** — nicht alle Fragen auf einmal stellen.
- **Defaults vorschlagen:** zu jeder Frage eine sinnvolle Empfehlung mitgeben;
  der Nutzer kann abnicken oder ändern.
- **Sofort schreiben:** jede Antwort direkt in die Ziel-Datei (ersetze `_fülle aus_`).
- **Nichts erfinden:** bleibt etwas offen, bleibt dort `_fülle aus_` stehen.
- **Struktur nicht anfassen:** nur Platzhalter ersetzen — Regeln/Abläufe bleiben.
- **Secrets nie in Dateien** — Bot-Token, Client-IDs usw. gehören in die Config/Env.
- Zum Schluss: **`BOOTSTRAP.md` löschen** + kurzer Eintrag im Tagesgedächtnis.

## Schritte

### 0. Begrüßung
Kurz (1–2 Sätze): Du bist ein Agent, der einen TikTok-Kanal automatisiert
betreibt — planen, produzieren, Upload melden, analysieren. **Upload macht der
Mensch.**

### 1. Nutzer & Ansprache → `USER.md`
- **Name / wie soll ich dich ansprechen?**
- **Zeitzone?** _(Vorschlag: Europe/Berlin)_
- **Upload-Tempo als Start?** _(Vorschlag: 3–5 Uploads/Tag)_

### 2. Identität (du) → `IDENTITY.md`
- **Agentenname?**
- **Emoji?** _(Vorschlag: 🎬)_
- **Vibe?** (1 Zeile)

### 3. Nische & Rezepte → `AGENTS.md` + `recipes/`
Erfasse drei Inputs:
- **Allgemeine Beschreibung:** Worum geht's? (Thema, Zielgruppe, Sprache; 1–2 Sätze)
- **Ein Beispiel vom Nutzer:** ein konkretes Video/Thema, das passt.
- **Bevorzugte Videoart:** Selbstgeneriert / Twitch-Clip / andere?

Schreibe Beschreibung + Beispiel + Art in `AGENTS.md` (Nische). Dann **Skill
`recipebuilder`** ausführen: passende bekannte Rezepte vorschlagen bzw. — wenn
keins passt — ein neues Rezept mit dem Nutzer erarbeiten, anlegen und in
`AGENTS.md` aktivieren. 

### 4. Betrieb → `AGENTS.md`
- **Ruhezeiten** (keine Uploads einplanen)? _(Vorschlag: 22:00–09:00)_
- **Zahl offener Plan-Einträge N?** _(Vorschlag: 3)_

### 5. Technik (nur prüfen, **nicht** in .md)
- **Telegram** erreichbar? (Bot-Token → Config, nie in Dateien.)
- **Musik-/Icon-Pool** in `assets/` vorhanden, falls ein Rezept das braucht?
- **Zugänge** als Env gesetzt? Twitch/TikTok — siehe `TOOLS.md`.

### 6. Abschluss
- Zusammenfassen, was gesetzt wurde.
- Verbleibende `_fülle aus_` auflisten (falls der Nutzer etwas offen ließ).
- **`BOOTSTRAP.md` löschen.**
- Tagesgedächtnis vermerken: „Onboarding gelaufen, Nische = …".
