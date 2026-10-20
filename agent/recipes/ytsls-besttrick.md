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
Position ist über das gesamte Video **identisch**. Es besitz folgende Unterregionen:
- `name` — Meist Oberste Box. Name des Skaters, für welchen der Inhalt dieser ScoreBox gilt.
- `score` — Direkt unter dem Namen, Enthält meistens ein Icon. Aktueller Trick Score erscheint hier, aber erst 15-20 sekunden nach dem Trick. 
- `list` — Rangliste
- Weitere Unterboxen können sein: Werbung, Icons, Übersichtsgrafiken.
> Auch Rangliste und Übersichtgrafiken enthalten Scoreanzeigen, diese sind jedoch nicht die Bewertung des AKtuellen Tricks.

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

> Score **nie nur** aus dem Transkript ableiten. Gute Kanidaten aus dem Transcript per OCR auf > auf `boxes.score`  bestätigen.


### Konkrete Clip-Auswahl
- **Länge:** **max. 40 s** — Anlauf + Trick + Landung + Reaktion + Bewertung.

- **Start-Anker = Score-Einblendung Vorgänger**, per OCR auf der festen `boxes.score` erkennen,
  Run up startet oft Kurz danach, zusätzlich Transkript prüfen bei langen Feiern oder Replay auch erst später.
- **End-Anker = Score-Einblendung** per OCR auf der festen `boxes.score`
  (`yt_clips.cli ocr --clip <id> --box <boxes.score> --step 1`): erster **stabiler** Treffer
  (0.0–10.0), **4–7 s danach** enden.
- **A oder B:**
  - **A — ein Fenster:** Score-Einblendung kommt **≤ 40 s** nach dem Trick →
    ein Fenster (Start vor dem Trick, Ende 4–7 s nach der Einblendung).
  - **Trick + Reaktion sind EIN Segment** — nicht in Trick / Gesicht / Score
    dreiteilen.
  - **B — zwei Fenster:** Sie kommt später → **Trick-Fenster** (~25 s: Anlauf
    bis Landung/Reaktion) + **Score-Fenster** (~15 s: 5–7 s vor der Einblendung
    bis 4–7 s danach). Gesamt ≤ 40 s. Im Rezept werden daraus zwei `clips[]`,
    die der Editor verkettet.
- **Schnittkanten:** vorher mit `editor.cli subtitles snap` auf **Satz-/Wortgrenzen**
  legen (bzw. `editor.cli subtitles cut --snap sentence`): Trick-Fenster endet an der
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
- **Action-Bereich (`action`)**: **eine Box pro Clip** welche den Skater über alle relevanten Kameras enthält.
- **Regel**: Höhe **immer maximale QuellHöhe**, Waagerecht verschieben, **nie** die Höhe beschneiden. (Bei h = 360 also `[x, 0, 202, 360]` )
- **Scoreboard als Kachel in der Ecke**: die vertikale `scoreboard`-Box als
  Region mit `fit: contain`, `size` passend zur Kachel, `position` in eine freie
  Ecke, Breite ≈ 25–35 % der Ausgabe. **Kein Band oben, keine volle Breite.**
  `score` und `name` müssen vollständig lesbar sein; `list` nur, wenn Platz ist.
  `boxes.score` bleibt die OCR-Box.
- Action **`cover`**, Kachel **`contain`**;
- **Keine zusätzliche Musik, Original-Audio behalten.**
- Nicht relevant: Werbung, Logo, Informationsblock.

### Bemerkungen
- **Immer prüfen, wessen Scoreboard angezeigt wird.** Zwischen Tricks Wechselt das Scoreboard, klar erkennbar unter `name`-box mittel OCR.
- Ansage (Transkript) und Anzeige (ScoreBaord) liegen **auseinander**.
  Fenster so legen, dass Trick → Reaktion → Score-Slot im Bild sind; Ende mit etwa 3sekunden Puffer **nach** dem Frame mit der Zahl im Scoreboard, nicht davor.

## Ton / Titel / Beschreibung
- Aus dem Transkript: **Trickname** und **Skater**.
- Titel-Muster: „`<Trick>` — `<Skater>` (`<Score>`)", knapp.
- Beschreibung: 1 Zeile + Hashtags.
- Hashtags: `#SLS` + `#<Skater>` + `#<Trick>`.

## Do / Don't
- Do: die Bewertung im Bild zeigen; Reaktion kurz mitnehmen.
- Don't: Bewertungen unter 8; lange Vorläufe oder mehrere Tricks in einem Clip.

## Beispiel: ein Clip in vier Aufrufen

```json
{
  "size": [1080, 1920], "fps": 30, "background": "#000000",
  "expect": {"ratio": "error"},
  "boxes": {"score": [1200, 80, 180, 90]},
  "clips": [{
    "source": "clips/sls-2025.mp4", "start": 1268, "end": 1301,
    "regions": [
      {"name": "action", "box": [690, 60, 540, 960], "size": [1080, 1920],
       "position": [0, 0], "fit": "cover"},
      {"name": "scoreboard", "box": [40, 20, 360, 900], "size": [320, 800],
       "position": [730, 60], "fit": "contain"}
    ]
  }]
}
```

Die Verhältnisse stimmen **exakt**: Action 540×960 → 1080×1920 (2×), Kachel
360×900 → 320×800 (0,889×). Also kein Beschnitt, keine Balken, keine Verzerrung —
`expect.ratio: error` erzwingt das. Die Action-Box wird pro Clip an 3 Frames
geprüft und bei Bedarf verschoben, nie gezoomt.

1. `yt_clips.cli next --recipe ytsls-besttrick` → Fenster + Clip-ID
2. `editor.cli validate --spec clips/besttrick-5.json`
3. `editor.cli render --spec clips/besttrick-5.json --overwrite`
4. `yt_clips.cli used --clip 5`
