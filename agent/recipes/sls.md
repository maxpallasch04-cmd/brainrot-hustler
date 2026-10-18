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
- Aktuelle Videos per Websearch, prüfe in der Datenbank ob das Video bereits behandelt wurde.

### Aufbau des Rohvideos
In SLS Competition Videos existiert ein schlankes Rechteckiges Scoreboard `Scoreboard`. Die Position ist über das Gesamte Video Identisch. Die Box besteht aus folgenden unterregionen:
- `name` des Skaters, 
- `score` / `logo` Enthält zu verschiedenen Zeiten SLS Logo oder Score des Tricks
- `list` (Rangliste),
- Werbung/Info (ignorieren).

### Zeitlicher Ablauf des Rohvideos
Meistens Zwei geteilt, erst Das Segment Lines und Anschließend das Segment Best Trick. 
Manchmal nur eines der Beiden.

## Clips 
### Auswahl Beste Momente
- **Phase: Best Trick** — der Teil **nach** den Lines. Erkennung anhand con: Ansage „best trick"/„best trick time" im Transkript oder YT Segmente.
- **Such-Anker: der Score.** Die Bewertung wird angesagt → Transkript-Zahlen
   und im Scoreboard angezeigt (OCR). **Bewertung < 8 ausschließen.**

### Konkrete Clip Auswahl
- **Länge:** **max. 40 s** — Trick + Reaktion + Bewertung.
- **Start-Anker = der Trick**, nicht der Score: Start beim **Anlauf/ vor dem Absprung**,
  mindestens **30 s vor der Score-Einblendung** (besser 50 s).
- **End-Anker = Score-Einblendung** per OCR auf der festen `boxes.score`
  erster **stabiler** Treffer (0.0–10.0) = End-Anker, nicht die Ansage.: **4–7 s danach** enden.
- **Lange Dauer zwischen Trick und Bewertung** Der Ursprungsclip Kann in Zwei Teile Geteilt   werden: ~25s Trick, ~15s Bewertung. Dabei nicht mitten in Kommentatorsätzen oder wörtern  schneiden.

### Clip Schnitt
- Finales Format 9:16
- Finde den 9:16 Bereich mit Maximaler Höhe, welcher im Trick abschnitt den Skater voll Enthält, meistens Mittig, das ist der Hauptbereich.
- Lege für die Zeit in welcher das Scoreboard zu sehen ist den gesamten `Scoreboard` bereich in eine Ecke (Also Video dieses Bereichs zur selbenzeit wie Hauptbereich)
- Keine extra Musik, Originalaudio Behalten.