---
name: ytsls-bestline
art: YT-Clip
theme: Skateboarding, SLS, Lines
---

# SLS Lines

Ein kompletter **Line-Run** aus dem SLS-Contest — vom Start des Runs bis zur
Bewertung.

## Auswahl
- **Quelle: SLS** (<https://www.youtube.com/@SLS>) — nur **volle Wettkämpfe**
  („Full Competition"), keine Einzel-Highlights.
- **Phase: Lines** — der Teil **vor** dem Best-Trick-Block. Erkennung (Tendenz,
  keine harte Grenze): Ansage „lines"/„run" im Transkript oder Text im Bild,
  gefolgt von mehreren **kompletten Runs** (mehrere Scores hintereinander). Der
  Best-Trick-Block beginnt erst mit der Ansage „best trick"/„best trick time".
- **Schnitt-Anker: der Score.** Die Bewertung wird angesagt → Transkript-Zahlen
  (`subtitles numbers`); an jeder Vergabe ist der Score auch im Scoreboard sichtbar.
- Ein Run dauert **typisch ≥ 45 s**, plus **~15 s bis zur Bewertung**.
  **Sturz → der Run ist kurz:** dann **keine Mindestlänge erzwingen** — die
  Score-Grenzen begrenzen den Run von selbst (zwischen zwei Scores = ein Run).
- **Bewertung > 8.**
- Sprache: Englisch.

## Format
- **Relevante Boxen** — Vision *erkennt*, das Text-Modell *wählt* anhand dieser Liste:
  - `Scoreboard` · **optional** (Region-Name `scoreboard`) — rechteckiger Kasten,
    geteilt in: Werbung, Name des aktuellen Skaters, Logo, Score, Liste anderer
    Skater, Informationsblock. _Nur ~30 % der Zeit da._
  - `Action-Bereich` · **required** (Region-Name `action`) — wo sich der Fahrer
    aufhält; Höhe > Breite, Höhe ≥ ½ Originalhöhe (nicht reinzoomen).
- **Aufteilung 9:16:** Action unten auf Breite setzen, freien Platz mit den
  restlichen Boxen füllen; ohne Platz: über/unter dem Action-Bereich, möglichst
  wenig Relevantes abschneiden. Gezeigt werden: Name, Score, Liste.
- **Fallback ohne Scoreboard:** nur `action`, füllt das Bild.
- **Nicht relevant / ignorieren:** Werbung, Logo, Informationsblock.
- Ausgabe: 9:16, Höhe ≥ 1280.

## Clips
- **Länge:** der ganze Run bis zur Bewertung (**typisch ≥ 60 s**, Score am Ende).
  **Keine harte Mindestlänge** — nach einem Sturz ist der Run kurz.
- **Anker:** Score. **Offset-Tendenz: eher später** (langer Run davor, Score am
  Ende des Clips).
- **Score:** **> 8** (darunter → Kandidat `Skipped`).
- **Schnitte nur, wo das Scoreboard sichtbar ist.**
- **Anzeige:** Score-Bereich **immer** mitzeigen (erstmal).
- Ein Clip pro Run.

## Musik
- **Original-Audio behalten.** Kein Musik-Mix.

## Schnitt / Overlays
- **Keine Overlays.**
- **Untertitel** (Englisch) einbrennen.
- Kein Zeitraffer — der Run bleibt in Echtzeit.

## Ton / Titel / Beschreibung
- Aus den Untertiteln: **Trick-Kombination** und **Skater**.
- Titel-Muster: „`<Skater>` fährt `<Score>`", knapp.
- Beschreibung: 1 Zeile + Hashtags.
- Hashtags: `#SLS` + `#<Skater>` + `#lines`.

## Do / Don't
- Do: den kompletten Run zeigen; die Bewertung am Ende.
- Don't: Runs mit Bewertung ≤ 8; mehrere Runs in einem Clip; harte Mindestlänge
  erzwingen (Sturz-Runs sind legitim kurz).

## Beispiele
- Kompletter Run einer Skaterin, sauber durchgezogen, danach Score-Einblendung „8.75".
