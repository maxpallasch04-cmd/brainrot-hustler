---
name:                # Rezept-ID == Dateiname (lowercase, kein _)
art: YT-Clip         # fix: wählt den Generierungsskill (ytclip)
theme:               # Thema/Tag fürs Plan-Matching
---

# <Rezeptname>

Ein, zwei Sätze: welche Videos, welcher Sport, was für Clips dabei herauskommen.

## Auswahl
- Quellen: YouTube-Kanal/-Kanäle oder Suchbegriffe (Vollspiele, Rohmaterial).
- Kriterium: was einen clipwürdigen Moment ausmacht (Tor, Foul, Jubel, Fehler …).
- Länge/Sprache der Quellvideos, Zeitfenster.

## Format
- **Relevante Boxen** — das Vision-Modell *erkennt* sie, das normale Modell *wählt*
  anhand dieser Liste aus. Pro Box: Name, Inhalt, **required/optional**.
  - `<Name>` · **required** — was drin steht/zu sehen ist (z. B. „Action-Bereich").
  - `<Name>` · **optional** — … (z. B. „Scoreboard, ~30 % der Zeit da").
    Unterboxen (falls die Box geteilt ist): `<Name>`, `<Name>`, …
- **Score-Box** — ist die Scoreboard-Box geteilt, die Unterboxen einzeln benennen
  (`score`, `name`, `list`) und **nur `score` rendern** — nie das ganze Board.
  `boxes.score` in **Quellkoordinaten** behalten: das ist später die **OCR-Box**.
  Die Box ist **statisch pro Video** — pro Clip kein Re-Detect, nur OCR (leer vs.
  Score).
- **Aufteilung 9:16 — lückenlos** — Reihenfolge und Größe der gewählten Boxen
  (z. B. „Scoreboard als Band oben, Action füllt den Rest"). Die Regionen füllen
  die Fläche **ohne schwarze Balken**; Hauptbox auf volle Breite, Rest für die
  Nebenboxen. `fit: cover` (füllt, behält Seitenverhältnis) — **nicht `stretch`**
  (verzerrt).
- **Action-Box — Hauptdarsteller bleibt drin** — er darf den Rand **nie berühren
  oder verlassen**: an jeder Seite **≥ 10 % Rand**. Im Zweifel Box vergrößern
  statt reinzoomen; bei wechselndem Bildausschnitt Box **pro Clip** neu setzen.
- **Fallback**, wenn eine **optionale** Box fehlt (z. B. „ohne Scoreboard: nur
  Action, füllt das Bild").
- Ausgabe: 9:16, Höhe ≥ 1280.
- **Nicht relevant / ignorieren:** … (Boxen, die nie ins Bild sollen).

## Clips
- **Muster/Phase** (Tendenz, **keine harte Grenze**): … (z. B. „erst Lines, danach
  Best Trick").
- **Such-Anker:** woran der Moment gefunden wird — Score / Trick / Audio-Peak.
- **Start-Anker:** das Ereignis selbst (Trick/Run/Absprung), **nicht** die
  Score-Ansage. Ansage/Einblendung nur als End-Anker; die Ansage kann deutlich
  später liegen — ein Start danach zeigt nur die Feier.
- **Offset-Tendenz:** früher oder später relativ zum Anker (z. B. „Start ≥ 10 s
  vor der Score-Einblendung, 2–4 s danach enden") — variiert pro Rezept.
- **Satzgrenzen:** an Satz-/Pausengrenze schneiden (`subtitles.cli cut --snap
  sentence`), nicht mitten in den Kommentar.
- **Ein Fenster oder zwei (A/B):** Liegt der Score nah am Ereignis, ein Fenster;
  kommt er später, **Ereignis-Fenster + Score-Fenster** als `segments` (hart
  aneinander, ohne Übergang). Beide Segmentkanten mit `snap` auf Satz-/Wortgrenzen
  legen — **nie mitten in einen Kommentatorsatz**, auch nicht am Übergang.
- **Prüfen:** Erster Frame = Ereignis (Trick/Run), nicht Jubel/Replay/Standbild.
- **Score:** Schwelle (z. B. `≥ 8`). Anzeige-Beginn per OCR auf der festen
  `boxes.score` (`yt_clips.cli ocr --clip <id>`), Werte 0.0–10.0; der erste
  **stabile** Treffer ist der End-Anker, nicht die Ansage.
- **Anzeige:** Score-Bereich **immer** mitzeigen (erstmal; später pro Clip wählbar).

## Musik
- Original-Audio behalten? Musik leise untermischen? Pool-Track rotieren?

## Schnitt / Overlays
- Clip-Länge (z. B. 15–25 s), Icon-Pool oder keins, Rausch-Filter.

## Ton / Titel / Beschreibung
- Tonalität, Titel-Muster, Beschreibungs-Muster, Hashtags.

## Do / Don't
- Do: …
- Don't: …

## Beispiele
Referenzen (Links/Pfade).
