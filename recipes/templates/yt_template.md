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
- **Aufteilung 9:16** — Reihenfolge und Größe der gewählten Boxen
  (z. B. „Scoreboard als Band oben, Action füllt den Rest"),
  `fit` (`stretch`/`contain`/`cover`) wenn nötig.
- **Fallback**, wenn eine **optionale** Box fehlt (z. B. „ohne Scoreboard: nur
  Action, füllt das Bild").
- Ausgabe: 9:16, Höhe ≥ 1280.
- **Nicht relevant / ignorieren:** … (Boxen, die nie ins Bild sollen).

## Clips
- **Muster/Phase** (Tendenz, **keine harte Grenze**): … (z. B. „erst Lines, danach
  Best Trick").
- **Schnitt-Anker:** worauf sitzt der Clip — Score / Trick / Audio-Peak.
- **Offset-Tendenz:** früher oder später relativ zum Anker (z. B. „eher später:
  bis 15 s nach dem Score") — variiert pro Rezept.
- **Score:** Schwelle (z. B. `≥ 8`) und Quelle (Transkript-Zahlen; OCR nur als
  Kontrolle).
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
