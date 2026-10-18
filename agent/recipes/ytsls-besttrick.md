---
name: ytsls-besttrick
art: YT-Clip
theme: Skateboarding, SLS, Best Trick
---

# SLS Best Trick

Kurzer, prägnanter Clip eines einzelnen **Best-Trick-Versuchs** aus dem SLS-Contest:
Trick, Reaktion und Bewertung in **max. 40 s**.

## Rohmaterial

### Auswahl der Rohvideos
- **Quelle: SLS** (<https://www.youtube.com/@SLS>) — nur **volle Wettkämpfe**
  („Full Competition"), keine Einzel-Highlights.
- Aktuelle Videos per Websearch suchen; vor der Auswahl in der Datenbank prüfen,
  ob das Video bereits behandelt wurde.

### Aufbau des Rohvideos
In SLS-Competition-Videos gibt es ein schlankes, rechteckiges `Scoreboard`. Die
Position ist über das gesamte Video **identisch**. Unterregionen:
- `name` — Skater
- `score` — enthält je nach Zeitpunkt SLS-Logo oder den Score des Tricks
- `list` — Rangliste
- Werbung/Info — ignorieren

### Zeitlicher Ablauf des Rohvideos
Meist zwei Segmente: erst **Lines**, anschließend **Best Trick**. Manchmal nur
eines von beiden.

## Clips

### Auswahl der besten Momente
- **Phase: Best Trick** — der Teil **nach** den Lines. Erkennung über die Ansage
  „best trick"/„best trick time" im Transkript oder die YT-Segmente.
- **Such-Anker: der Score.** Die Bewertung wird angesagt → Transkript-Zahlen
  (`subtitles numbers`) und im Scoreboard angezeigt (OCR).
  **Bewertung < 8 ausschließen.**
- Sprache: Englisch.

### Konkrete Clip-Auswahl
- **Länge:** **max. 40 s** — Trick + Reaktion + Bewertung.
- **Start-Anker = der Trick**, nicht der Score: Start beim **Anlauf/vor dem
  Absprung**. Die Ansage ist **kein** Startanker — sie kann weit nach dem Trick
  liegen (Fehlerbild: Start bei der Ansage → nur Feier).
- **End-Anker = Score-Einblendung** per OCR auf der festen `boxes.score`
  (`yt_clips.cli ocr --clip <id> --step 1`): erster **stabiler** Treffer
  (0.0–10.0), **4–7 s danach** enden.
- **A oder B:**
  - **A — ein Fenster:** Score-Einblendung kommt **≤ 40 s** nach dem Trick →
    ein Fenster (Start vor dem Trick, Ende 4–7 s nach der Einblendung).
  - **B — zwei Fenster:** Sie kommt später → **Trick-Fenster** (~25 s: Anlauf
    bis Landung/Reaktion) + **Score-Fenster** (~15 s: 5–7 s vor der Einblendung
    bis 4–7 s danach). Gesamt ≤ 40 s. `yt_clips.cli clip` rendert beide Segmente
    und hängt sie zusammen.
- **Schnittkanten:** vorher mit `subtitles.cli snap` auf **Satz-/Wortgrenzen**
  legen (bzw. `subtitles.cli cut --snap sentence`): Trick-Fenster endet an der
  Satzgrenze **nach der Landung/Reaktion**, Score-Fenster beginnt an der
  Satzgrenze **vor der Einblendung** (sonst mindestens auf einem Wortanfang).
  **Nie mitten in Kommentatorsätze oder Wörter schneiden** — auch nicht am
  Übergang Trick → Score.
- **Prüfen:** Der erste Frame zeigt **Anlauf/Trick**, nicht Jubel, Replay oder
  Standbild. Sonst Fenster nach vorne ziehen. Bei B: erstes Segment = Trick,
  zweites = Score-Einblendung.
- **Ein Clip pro Versuch** — kein Aneinanderhängen mehrerer Tricks.

### Clip-Schnitt (9:16)
- Finales Format **9:16**, Höhe **≥ 1280**.
- **Action-Bereich (`action`)**: 9:16-Ausschnitt mit **maximaler Höhe**, der den
  Skater im Trick **vollständig** enthält — meist mittig. Die Box zeigt den
  **ganzen** Trick (Anlauf, Absprung, Flug, Landung); Höhe > Breite, Höhe
  ≥ ½ Originalhöhe. Der Fahrer darf den Rand **nie berühren oder verlassen**:
  an **jeder Seite ≥ 10 % Rand** (bei 1080 px Ausgabebreite ≥ 110 px).
  Im Zweifel Box **vergrößern** statt reinzoomen. 3–5 Frames aus dem
  Trickfenster prüfen; passt es nicht → Box **pro Clip** neu setzen
  (`yt_clips.cli format-set --clip`).
- **Scoreboard während der Score-Zeit**: den `Scoreboard`-Bereich als
  Einblendung in eine **Ecke** legen (Region mit `box` + `size` + `position`
  + `start`/`duration`), gleichzeitig mit dem Action-Bereich. `score` und `name`
  müssen vollständig lesbar sein; `list` nur, wenn der Platz reicht.
  `boxes.score` bleibt die OCR-Box.
- **Fallback ohne Scoreboard:** nur `action`, füllt das Bild.
- `fit` immer **`cover`**, **nie** `stretch`.
- **Keine zusätzliche Musik, Original-Audio behalten.**
- Nicht relevant: Werbung, Logo, Informationsblock.

## Ton / Titel / Beschreibung
- Aus dem Transkript: **Trickname** und **Skater** (keine eingebrannten Untertitel).
- Titel-Muster: „`<Trick>` — `<Skater>` (`<Score>`)", knapp.
- Beschreibung: 1 Zeile + Hashtags.
- Hashtags: `#SLS` + `#<Skater>` + `#<Trick>`.

## Do / Don't
- Do: die Bewertung im Bild zeigen; Reaktion kurz mitnehmen.
- Don't: Bewertungen unter 8; lange Vorläufe oder mehrere Tricks in einem Clip.

## Beispiele
- Best Trick Kickflip Backside Tailslide → Jubel → Score-Einblendung „9.10".
