# MEMORY.md — Fixliste (von Max gepflegt)

> Max schraubt konstant an Modulen und Rezepten. Diese Datei ist die **Fixliste**:
> wiederkehrendes Feedback zu Clips/Format, das noch nicht in Skript/Rezept
> eingearbeitet ist. Eintrag rein, wenn Feedback kommt; Max arbeitet es ab.

## Offene Punkte (YT-Clips / SLS)

- [ ] **Keine schwarzen Ränder im Hochformat.** Die Regionen-Aufteilung muss die
      volle 1080×1920-Fläche **lückenlos** füllen (Scoreboard + Action), keine
      (großen) Lücken. Regionen nicht stumpf nebeneinander stapeln — Action auf
      volle Breite, Scoreboard in den Rest. _Quelle: Feedback 2026-10-17._
      _Fehlerbild: mein Format-Mapping `action=[260,0,1020,720]` + `scoreboard=[60,60,200,550]` → horizontale schwarze Balken._
- [ ] **Scoreboard sichtbar + gut platziert** — Score **und** Action gleichzeitig
      im Hochformat, beides lesbar, Score nicht abgeschnitten/zu klein.
- [ ] **Clip muss die Action enthalten, nicht nur die Feier.** Clip-Start
      **deutlich vor** der Score-Ansage (Trick/Landung + Reaktion + Score).
      _Fehlerbild: Start 352 s bei Score-Ansage 360 s → nur Feier, kein Trick._
- [ ] **`stretch` verzerrt unschön → `cover` verwenden.** Action auf 1080×1920
      mit `fit: cover` (füllt, behält Seitenverhältnis, croppt seitlich) statt
      `stretch` (exakt, verzerrt). _Quelle: 2026-10-17._
- [ ] **Replay/Standbild nicht als Clip-Anfang nehmen.** Fenster 1 war ein
      **Replay mit ~3 s Standbild** am Anfang, Trick nicht ganz drauf. Der
      **Live-Trick** muss vollständig drin sein (Start deutlich vor dem Absprung,
      vor dem Standbild/Replay-Einsatz). _Quelle: 2026-10-17._
- [ ] **Scoreboard pro Clip/Quelle präziser bestimmen statt einmal pro Video.**
      SLS verschiebt/skaliert das Board je Szene → die gespeicherte Box passt im
      Score-Fenster nicht → abgeschnitten. Vorgehen: **pro Clip** Score-Box neu
      croppen (`crop-frame --scale 2`) + OCR auf dem Crop über ein **1-s-Zeitraster**.
      _Quelle: 2026-10-17._

## Modul-Fixes (für Max)

- [ ] **`ocr`-Befehl im Interface fehlt.** Den Score-Einblendzeitpunkt („ab wann
      steht der Score im Scoreboard?") konnte ich nur über Vision auf der
      Score-Box bestimmen — teuer und ungenau. Ein günstiger OCR-Befehl (z. B.
      `yt_clips.cli ocr --box <score-box> --at <t,…>` auf der Score-Region) würde
      den Anzeige-Beginn exakt liefern. _Quelle: 2026-10-17._
- [ ] **`video_generation` `layout`/`compose`: `opacity`-Feld hängt ffmpeg auf.**
      Eine Region mit `"opacity": 1.0` (Alpha-Compositing) → `BrokenPipeError`
      mitten im Schreiben → korrupte `.mp4` (`moov atom not found`).
      Workaround: `opacity` erstmal weglassen (Regionen ohne das Feld rendern
      sauber). _Quelle: 2026-10-17, Zwei-Regionen-Layout (action + scoreboard)._
- [ ] **`scoreboard`-Box ist statisch (ein Format pro Video).** SLS wechselt
      Layout/Skalierung je nach Szene (Action vs. Interview/Replay) → die eine
      gespeicherte Box passt im Score-Fenster nicht mehr → **Scoreboard
      abgeschnitten**. Nötig: **Box pro Szene/Clip** statt eines Formats pro
      Video. Alternativ Box **relativ** speichern (Anteile der Frame-Größe),
      dann skaliert sie mit. _Quelle: 2026-10-17._
- [ ] **Keine Progress-/Heartbeat-Ausgabe bei `layout`/`render`.** Lange Renders
      (1020×720 → 1080×1920, preset=medium, mehrere Minuten) sehen aus wie
      „hängt". Ich habe sie fälschlich gekillt → abgebrochene `.mp4`. Ein
      Progress-Signal oder ein „läuft noch"-Hinweis über die CLI würde
      Fehl-Kills verhindern. _Quelle: 2026-10-17 (Max' Timeout-Verdacht bestätigt)._
- [ ] **Replay/Live/Standbild nicht unterscheidbar.** Fenster 1 war ein
      **Replay mit Standbild am Anfang** — das Modul liefert kein Signal, welcher
      Zeitbereich Live-Trick vs. Wiederholung vs. Highlight-Package ist. Eine
      billige **Szene-/Shot-Erkennung** (Cut + Standbild + „Replay"-Einblendung)
      würde helfen, nur den Live-Moment zu wählen. _Quelle: 2026-10-17._
- [ ] **Keine wortgenauen Transkript-Zeitstempel.** `subtitles numbers` liefert
      nur Cue-Blöcke → ich schneide mitten in den Sprechfluss der Kommentatoren.
      Nötig: **Wort-/Satzgrenzen** (Wort-Zeitstempel), um an Pausen/Satzenden zu
      schneiden statt mitten im Satz. _Quelle: 2026-10-17._
- [ ] **Schnitt nicht im Sprechfluss** — als Rezept-Regel: an Satz-/Pausengrenze
      schneiden, nicht mitten in einen Satz des Kommentators. _Quelle: 2026-10-17._

## Kontext
- 2026-10-17: Erster Pipeline-Durchlauf (`ytsls-besttrick`, SLS Tempe, 9.5 Braden
  Hoban). Download-Fix von Max hat den Bot-Check gelöst. Format + Timing = Fehler.
- 2026-10-17: Layout-Fix erprobt — Action `stretch` auf 1080×1920 (full-bleed),
  Scoreboard oben links überlagert → **keine schwarzen Ränder** mehr. Offen:
  `stretch` verzerrt leicht; `cover` wäre eleganter (croppt seitlich).
- 2026-10-17: Timing-Lernen — Score wird **viel später** gezeigt/angesagt als der
  Trick (hier: Trick ~305 s, Score-Anzeige erst ~326 s, Ansage 360 s). Anker `A`
  (ein Rutsch) wird dann zu lang → **Option C** (zwei Fenster concat: Trick + Score).
  Score-Anzeige-Beginn nur per Vision/OCR prüfen, nie aus der Ansage ableiten.
- 2026-10-17: Option C erprobt (Trick-Fenster + Score-Fenster concat). Feedback:
  Fenster 1 = **Replay mit ~3 s Standbild**, Trick nicht ganz drauf; `stretch`
  verzerrt unschön (`cover` besser); Scoreboard im Score-Fenster **links
  abgeschnitten**. Timeout war real (~7200) — lange Renders nicht killen.
  Scoreboard-Bestimmung künftig: **pro Clip neu croppen** (`crop-frame --scale 2`)
  + OCR auf dem Crop über ein 1-s-Zeitraster.
