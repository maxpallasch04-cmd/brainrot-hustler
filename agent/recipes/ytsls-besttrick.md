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
- **Phase: Best Trick** — der Teil **nach** den Lines. Erkennung (Tendenz, keine
  harte Grenze): Ansage „best trick"/„best trick time" im Transkript oder Text im
  Bild; danach **einzelne** Trick-Versuche mit je eigenem Score (statt kompletter
  Runs).
- **Such-Anker: der Score.** Die Bewertung wird angesagt → Transkript-Zahlen
  (`subtitles numbers`) und im Scoreboard angezeigt (OCR). **Start-Anker ist aber
  der Trick**, nicht die Ansage.
- **Bewertung < 8 ausschließen.**
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
- **Aufteilung 9:16 — lückenlos:** `score` als Band **oben auf volle Breite
  (1080 px)**, Richtwert **300 px hoch** (200–400; Ziffern vollständig lesbar, nicht
  abgeschnitten), `fit: cover`. Action darunter, füllt den **Rest bis 1920** — keine
  Lücke. Mit `name`/`list`: je ein schmales Band (120–180 px), Action entsprechend
  kleiner. `fit` immer **`cover`**, **nie `stretch`**.
- **Action-Box — der Fahrer bleibt drin:** Die Box zeigt den **ganzen** Trick
  (Anlauf, Absprung, Flug, Landung). Der Fahrer darf den Rand **nie berühren oder
  verlassen**: an **jeder Seite ≥ 10 % Rand** (bei 1080 px Ausgabebreite ≥ 110 px).
  Im Zweifel Box **vergrößern** statt reinzoomen. 3–5 Frames aus dem Trickfenster
  prüfen; passt es nicht → Box **pro Clip** neu setzen (`format-set --clip`).
- **Fallback ohne Scoreboard:** nur `action`, füllt das Bild.
- **Nicht relevant / ignorieren:** Werbung, Logo, Informationsblock.
- Ausgabe: 9:16, Höhe ≥ 1280.

## Clips
- **Länge:** **max. 20 s** — Trick + Reaktion + Bewertung.
- **A oder B:**
  - **A — ein Fenster:** Die Score-Einblendung kommt **≤ 20 s** nach dem Trick →
    ein Fenster (Start vor dem Trick, Ende 2–4 s nach der Einblendung).
  - **B — zwei Fenster:** Sie kommt später → **Trick-Fenster** (Anlauf bis
    Landung/Reaktion, ~8–12 s) + **Score-Fenster** (1 s vor der Einblendung bis
    2–4 s danach), **hart aneinander** (kein Übergang). Gesamt ≤ 20 s.
    `yt_clips.cli clip` rendert beide Segmente und hängt sie zusammen.
  - **B — Schnittkanten:** Beide Kanten vorher mit `subtitles.cli snap` auf
    **Satz-/Wortgrenzen** legen: Trick-Fenster endet an der Satzgrenze **nach der
    Landung/Reaktion**, Score-Fenster beginnt an der Satzgrenze **vor der
    Einblendung** (sonst mindestens auf einem Wortanfang). **Nie mitten in einen
    Kommentatorsatz schneiden** — auch nicht am Übergang Trick → Score.
- **Start-Anker = der Trick**, nicht der Score: Start beim **Anlauf/Absprung**,
  mindestens **10 s vor der Score-Einblendung** (besser 15 s). Die **Ansage** ist
  kein Startanker — sie kann **30–60 s nach dem Trick** liegen (Fehlerbild: Start
  352 s bei Ansage 360 s → nur Feier). Score-**Einblendung** (OCR) ist der
  End-Anker: **2–4 s danach** enden.
- **Prüfen:** Der erste Frame zeigt **Anlauf/Trick**, nicht Jubel, Replay oder
  Standbild. Sonst Fenster nach vorne ziehen. Bei B: erstes Segment = Trick,
  zweites = Score-Einblendung.
- **Score:** **≥ 8** (darunter → Kandidat `Skipped`).
- **Schnitte nur, wo das Scoreboard sichtbar ist.**
- **Score-Anzeige:** per OCR auf der festen `boxes.score`
  (`yt_clips.cli ocr --clip <id> --step 1`); erster **stabiler** Treffer
  (0.0–10.0) = End-Anker, nicht die Ansage.
- **Satzgrenzen:** an Satz-/Pausengrenze schneiden (`subtitles.cli cut --snap
  sentence`), nicht mitten in den Kommentar.
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
