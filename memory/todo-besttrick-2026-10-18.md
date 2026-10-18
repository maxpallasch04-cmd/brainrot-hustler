# TODOLISTE — Best-Trick-Clip & Annahmen (Stand 2026-10-18, rev. 2)

**Auftrag von Max: NICHTS an Rezepten/Skills/CLI ändern. Alles nur hier im Memory
festhalten.** Kein Render, kein Upload, keine Pipeline für diesen Clip bis Max' Go.
Rev. 2 enthält Max' Klarstellungen zu A1–A7 (wörtlich sinngemäß).

## Fakten (gemessen, nicht geschätzt)

Quelle `clips/dJLTd0x8XOo.mp4` (SLS Tempe 2026, Men's Final, Best Trick), 1280x720:

- **2572**: Weitwinkel — Skater x 340–480 (in 640er Koordinaten; skaliert 680–960 von 1280),
  Helfer davor, nur ≈ ¼ Bildhöhe.
- 2575–2577,8: **GoPro-Standbild** (Frames identisch) — kein Material.
- 2578,0 Kante, 2578,5 in der Luft, ~2579,5 Landung. **Trick-Kern ≈ 2578,0–2579,5.**
- 2580: Close-up Jubel **richtig mittig** (640er: x 150–430 → 1280er: 300–860), füllt ganze Höhe.
- 2585/2590: Close-up lachend, mittig-rechts (640er x 270–560 → 1280er 540–1120).
- 2593–2596: Score-Kachel **9.5** links oben (1280er x 55–250, y 75–470), Skater daneben mittig.
- **Erkenntnis Max (bestätigt durch 2580): Der Skater ist in den relevanten
  Kamera-Regionen fast immer in der MITTE.** Die Box muss die Union über alle
  relevanten Szenen abdecken — nicht eine Szene, nicht das ganze Panel.

## A) Annahmen, die zum Fehler geführt haben (Memory, nicht Skill-Änderung)

- [ ] A1 **Höhe zuerst, nicht Breite.** Max: „Breite ist klar, aber du zoomst rein —
  hier wird Höhe abgeschnitten, das führt zu kleinerer Gesamtbreite."
  Richtig: `cover` auf eine 9:16-Box schneidet die **Höhe** ab (720 → ~405 Quellhöhe
  genutzt) → das Bild wird insgesamt kleiner/weicher statt größer. Für volle
  Originalhöhe: **`contain`** (oder Box mit Höhe 720 und Breite = Union-Breite).
  Meine Denkweise („Box breiter machen") war falsch herum.

- [ ] A2 **Score-Kachel ist eine vertikale Kachel** (Stake / Name / 9.5 / Versuche /
  Standings), kein horizontales Band. Max' Lösung: **Action 9:16 voll, Kachel als
  Ausschnitt in die Ecke legen.** Rezept fordert dagegen „Band oben, volle Breite,
  300 px" → falsche Vorgabe für SLS.

- [ ] A3 **„A oder B" ist Trick + Reaktion zusammen, sonst zwei Clips — nicht drei.**
  Meine Dreiteilung (Trick / Gesicht / Score) war Erfindung. Offene Frage an Max:
  **Verbietet das Rezept Übergänge?** (Text sagt nichts dagegen, ich habe es als
  hart aneinander interpretiert.) → Klären, nicht selbst entscheiden.

- [ ] A4 **Keine Sonderregel pro Kamera nötig.** Max: „TOTAL EGAL — finde die Region,
  die über alle relevanten Kamera-Regionen den Skater enthält, meistens die Mitte."
  Also: **eine Union-Box pro Clip**, mittig, `contain` → alle Perspektiven drin.
  Meine „Format pro Szene"-Diskussion ist damit erledigt.

- [ ] A5 **Timing:** Start-Anker = erster bewegter Frame. Max: „Der Trick ist da noch
  lange nicht vorbei … es fehlen vorne und hinten locker 5 Sekunden" → Fenster muss
  **Anlauf + Trick + Landung** enthalten, nicht nur Absprung.

- [ ] A6 **Mein Fehler, nicht des Rezepts.** Erster-Frame-/Frame-Diff-Prüfung stand im
  Skill, ich habe sie übergangen. Ich habe Frames geschätzt statt gemessen.

- [ ] A7 **Untertitel-Defekt nur MERKEN.** Max fixt selbst im CLI (`cut --snap sentence`
  → 59 Fragment-Cues mit 34-ms-Lücken, `burn` ohne sichtbares Ergebnis). Keine
  Änderung von mir.

## B) Vorschlag zur Rezept-Regel „Action-Box" (nur Vorschlag, Max entscheidet)

Ist in `memory/proposal-action-box-rule.md` separat formuliert (Union-Box über alle
Szenen, Höhe = Originalhöhe, Mitte als Default, `contain` statt Panel-`cover`).

## C) Zustand Dateien

- [ ] C1 `modules/final_subs.mp4`, `preB.mp4`, `aA/aB/aB1/aB1b/aB2/aB2c.mp4` = Zwischenstände, verworfen.
- [ ] C2 `contentplan.md` Eintrag 2026-10-18 14:00 → Status zurück auf `geplant`, `datei` leer.
- [ ] C3 `longterm_memory` id 1 beschreibt falschen Clip → korrigieren oder löschen.
- [ ] C4 R2 enthält nur `preB.mp4` (R2_KEEP=1), wird beim nächsten Upload ersetzt.

## D) Offene Fragen (blockieren Neuaufbau)

- [ ] D1 Übergänge erlaubt? (A3)
- [ ] D2 Kachel-Position in der Ecke: oben links / oben rechts / unten?
- [ ] D3 Reaktion rein oder nur Trick + Score?
- [ ] D4 Fensterlänge: wie viele Sekunden vor dem Absprung / nach der Landung?
