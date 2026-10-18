# Vorschlag — Regel „Action-Box" für YT-Clips (nur Vorschlag, nichts geändert)

Stand 2026-10-18. Betrifft `recipes/ytsls-besttrick.md` / `ytsls-bestline.md`,
Abschnitt `## Format`, Punkt „Action-Bereich". **Nicht aktiv** — Max entscheidet.

## Problem der aktuellen Formulierung

> `Action-Bereich` · required — wo sich der Fahrer aufhält; Höhe > Breite,
> Höhe ≥ ½ Originalhöhe

Diese Formulierung lässt zwei falsche Lesarten zu, beide sind passiert:

1. **Panel-Lesart:** „wo sich der Fahrer aufhält" = das ganze 16:9-Panel
   `[0,0,1280,720]`. Folge bei `fit: cover` auf 9:16: es wird **Höhe** abgeschnitten
   (720 Quellzeilen → ~405), das Ergebnis ist kleiner und weicher, nicht größer.
2. **Szenen-Lesart:** Box pro Kamerawechsel neu. Folge: 9:16-Crops springen,
   Gesichter wandern aus dem Bild, das Scoreboard fällt raus.

## Vorschlag (Ersatztext)

> **Action-Box = Union über alle Szenen des Clips.**
> 1. 5–8 Frames gleichmäßig über das Clip-Fenster ziehen und im **Original** ansehen.
> 2. Pro Frame den Akteur markieren (x_min, x_max, y_min, y_max).
> 3. **Union** aller Akteurs-Boxen bilden → das ist die Action-Box. Default: Mitte.
> 4. **Höhe = Originalhöhe** (nicht beschneiden). Die Breite folgt aus der Union.
> 5. `fit: contain` auf 9:16, Hintergrund unscharf aufgefüllt (kein Schwarz).
>    Nur wenn die Union ≤ 405 px breit ist, ist `cover` erlaubt (dann kein Verlust).
> 6. QC: 3 Frames aus dem Fenster (Anfang/Mitte/Ende) — Akteur vollständig sichtbar,
>    ≥ 10 % Rand je Seite. Sonst Union erweitern, nicht zuschneiden.

## Score-Kachel (A2, hängt zusammen)

> Scoreboard ist bei SLS eine **vertikale Kachel** (~195x400 von 1280x720).
> Nicht als Band rendern. Stattdessen: Kachel als Standbild croppen
> (`frames --at` + `crop`), als PNG speichern, per `overlay` in eine **Ecke**
> (~20–25 % Breite, oben links Default). Action bleibt vollflächig 9:16.

## Begründung in einem Satz

Nicht die Box „größer machen" löst das Problem, sondern **die Höhe unangetastet
lassen** und die Breite aus der Union der Akteurspositionen ableiten — dann passen
alle Perspektiven rein, ohne zusätzlichen Zoom.
