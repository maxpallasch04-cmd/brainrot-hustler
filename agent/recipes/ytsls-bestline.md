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
- **Such-Anker: der Score.** Die Bewertung wird angesagt → Transkript-Zahlen
  (`subtitles numbers`) und im Scoreboard angezeigt (OCR). **Start-Anker ist der
  Run-Beginn**, nicht die Ansage.
- Ein Run dauert **typisch ≥ 45 s**, plus **~15 s bis zur Bewertung**.
  **Sturz → der Run ist kurz:** dann **keine Mindestlänge erzwingen** — die
  Score-Grenzen begrenzen den Run von selbst (zwischen zwei Scores = ein Run).
- **Bewertung > 8.**
- Sprache: Englisch.

## Format
- **Relevante Boxen** — Vision *erkennt*, das Text-Modell *wählt* anhand dieser Liste:
  - `Scoreboard` · **optional** — nur der Container; **nicht als Ganzes rendern**.
    Unterboxen: `score` (Zahlenkasten), `name` (Skater), `list` (Rangliste),
    Werbung/Logo/Info (ignorieren). _Nur ~30 % der Zeit da._
  - `score` · **required, wenn das Scoreboard sichtbar ist** (Region-Name `score`) —
    genau der Kasten mit dem **tatsächlichen Score**. Er wird angezeigt **und** ist
    die **OCR-Box** (Quellkoordinaten in `boxes.score` speichern), nicht das Board.
    Die Box ist **statisch pro Video** — kein per-Clip-Re-Detect; pro Clip nur OCR
    (leer vs. Score).
  - `name` / `list` · **optional** — nur wenn Platz; schmale Bänder.
  - `Action-Bereich` · **required** (Region-Name `action`) — wo sich der Fahrer
    aufhält; Höhe > Breite, Höhe ≥ ½ Originalhöhe — lieber **größer** als
    reinzoomen.
- **Aufteilung 9:16 — volle Höhe, kein Beschnitt:** **eine Box** (`action`), die
  den Skater über den ganzen Run enthält. Die Box ist **9:16 in voller
  Quellhöhe** (Breite = Höhe × 9/16), `fit: cover`, `position: center` → füllt
  1080x1920, **keine schwarzen Ränder, kein zusätzlicher Beschnitt**. Eine
  breitere Box wird von `cover` seitlich beschnitten; `contain` erzeugt Balken.
- **Scoreboard als Kachel in der Ecke:** `scoreboard` mit `fit: contain`, `size`
  passend zur Kachel, `position` in eine freie Ecke, Breite ≈ 25–35 % der
  Ausgabe — **kein Band oben, keine volle Breite**. `boxes.score` bleibt die
  OCR-Box.
- **Action-Box — der Fahrer bleibt drin:** Der Fahrer darf den Rand **nie
  berühren oder verlassen**: an **jeder Seite ≥ 10 % Rand** (bei 1080 px
  Ausgabebreite ≥ 110 px). Im Zweifel Box **vergrößern** statt reinzoomen.
  3–5 Frames aus dem Run prüfen; passt es nicht → Box **pro Clip** neu setzen
  (eigenes Rezept für diesen Clip).
- **Fallback ohne Scoreboard:** nur `action`, füllt das Bild.
- Action **`cover`**, Kachel **`contain`**; `stretch` verzerrt.
- **Nicht relevant / ignorieren:** Werbung, Logo, Informationsblock.
- Ausgabe: 9:16, Höhe ≥ 1280.

## Clips
- **Länge:** der ganze Run bis zur Bewertung (**typisch ≥ 60 s**, Score am Ende).
  **Keine harte Mindestlänge** — nach einem Sturz ist der Run kurz.
- **A oder B:**
  - **A — ein Fenster:** Score-Einblendung direkt am Run-Ende → ganzer Run in
    einem Fenster.
  - **B — zwei Fenster:** Score kommt deutlich später → **Run-Fenster** +
    **Score-Fenster** (1 s vor der Einblendung bis 2–4 s danach), **hart
    aneinander** (kein Übergang). Beide Kanten mit `editor.cli subtitles snap` auf
    **Satz-/Wortgrenzen** legen: Run-Fenster endet an der Satzgrenze **nach dem
    Run**, Score-Fenster beginnt an der Satzgrenze **vor der Einblendung**.
    **Nie mitten in einen Kommentatorsatz schneiden** — auch nicht am Übergang
    Run → Score.
- **Start-Anker = Run-Beginn**: Start beim Anlauf/ersten Trick, die
  Score-Einblendung ist der End-Anker (**2–4 s danach** enden). Die **Ansage** ist
  kein Startanker — sie kann **deutlich später** liegen; ein Start danach zeigt
  nur die Feier.
- **Prüfen:** Der erste Frame zeigt den **laufenden Run**, nicht Jubel, Replay
  oder Standbild.
- **Score:** **> 8** (darunter → Kandidat `Skipped`).
- **Schnitte nur, wo das Scoreboard sichtbar ist.**
- **Score-Anzeige:** per OCR auf der festen `boxes.score`
  (`yt_clips.cli ocr --clip <id> --step 1`); erster **stabiler** Treffer
  (0.0–10.0) = End-Anker, nicht die Ansage.
- **Satzgrenzen:** an Satz-/Pausengrenze schneiden (`editor.cli subtitles cut --snap
  sentence`), nicht mitten in den Kommentar.
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
