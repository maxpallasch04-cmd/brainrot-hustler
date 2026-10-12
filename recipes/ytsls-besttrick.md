---
name: ytsls-besttrick
art: YT-Clip
theme: Skateboarding, SLS, Best Trick
---

# SLS Best Trick

Kurzer, prägnanter Clip eines einzelnen **Best-Trick-Versuchs** aus dem SLS-Contest:
Trick, Reaktion und Bewertung in **max. 20 s**.

## Auswahl
- **Quelle: SLS** (<https://www.youtube.com/@SLS>) — nur **volle Wettkämpfe**
  („Full Competition"), keine Einzel-Highlights.
- **Phase: Best Trick** — der Teil **nach** den Lines. Die Grenze ist eine
  **Tendenz** (Ansage im Transkript/Text im Bild), **keine harte**.
- **Schnitt-Anker: der Score.** Die Bewertung wird angesagt → Transkript-Zahlen
  (`subtitles numbers`); an jeder Vergabe ist der Score auch im Scoreboard sichtbar.
- **Bewertung < 8 ausschließen.**
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
- **Länge:** **max. 20 s** — Trick + Reaktion + Bewertung.
- **Anker:** Score. **Offset-Tendenz: eher früher** (Start vor dem Score, damit
  Trick und Reaktion mit drin sind; kurz nach der Einblendung enden).
- **Score:** **≥ 8** (darunter → Kandidat `Skipped`).
- **Schnitte nur, wo das Scoreboard sichtbar ist.**
- **Anzeige:** Score-Bereich **immer** mitzeigen (erstmal).
- Ein Clip pro Versuch — kein Aneinanderhängen.

## Musik
- **Original-Audio behalten.** Kein Musik-Mix.

## Schnitt / Overlays
- **Keine Overlays.**
- **Untertitel** (Englisch) einbrennen.

## Ton / Titel / Beschreibung
- Aus den Untertiteln: **Trickname** und **Skater**.
- Titel-Muster: „`<Trick>` — `<Skater>` (`<Score>`)", knapp.
- Beschreibung: 1 Zeile + Hashtags.
- Hashtags: `#SLS` + `#<Skater>` + `#<Trick>`.

## Do / Don't
- Do: die Bewertung im Bild zeigen; Reaktion kurz mitnehmen.
- Don't: Bewertungen unter 8; lange Vorläufe oder mehrere Tricks in einem Clip.

## Beispiele
- Best Trick Kickflip Backside Tailslide → Jubel → Score-Einblendung „9.10".
