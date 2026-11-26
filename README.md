# Spyro Trilogy

Native PC-Ports der drei PlayStation-Spyro-Spiele (PAL/Europa) – **ohne Emulation**,
gebaut aus deinen **eigenen** Discs.

*English summary below.*

Spyro Trilogy ist eine Windows-App, die aus Disc-Images von Spyro the Dragon,
Spyro 2: Gateway to Glimmer und Spyro: Year of the Dragon per statischer
Rekompilierung ([PSXRecomp](https://github.com/mstan/psxrecomp)) native PC-Spiele
baut und startet. Dieses Repository enthält **keine Spieldaten, keinen
Spielcode und keine fertigen Spiele** – alles entsteht erst auf deinem PC aus
deinen Images.

## Was die App kann

- **Einrichtung mit Oberfläche:** Images (oder einen Ordner) wählen, die App
  erkennt und prüft sie (Seriennummer, Größe, SHA-1, LibCrypt-`.sbi`) und baut
  die gewählten Spiele.
- **Bibliothek:** alle drei Spiele starten und einstellen – mit Maus,
  Tastatur oder Controller.
- **Einstellungen pro Spiel:** Vollbild, VSync, interne Auflösung (bis 8×),
  Kantenglättung, Texturfilter, Wackel-Korrektur (PGXP), Röhrenfilter,
  Lautstärke sowie Tastatur- und Controllerbelegung.
- **Spielmenü im Spiel** (F10 · Strg+L · Select+L3) im Stil der App.
- **Sprachen:** Deutsch und Englisch.

## Unterstützte Discs

| Spiel | Serial | Hinweis |
|---|---|---|
| Spyro the Dragon | SCES-01438 | |
| Spyro 2: Gateway to Glimmer | SCES-02104 | `.sbi` nötig |
| Spyro: Year of the Dragon | SCES-02835 | `.sbi` nötig |

Images als `.cue` + `.bin` (Redump-Stand). Bei Spyro 2 und 3 muss die passende
`.sbi`-Datei mit gleichem Namen neben der `.cue` liegen.

## Benutzen

1. Fertige App herunterladen (Releases) oder selbst paketieren (siehe unten).
2. `Spyro Trilogy.exe` starten → **Einrichtung starten** → Images wählen →
   **Spiele bauen**. Beim ersten Mal lädt die App einmalig ihre Werkzeuge
   (Python, Clang/CMake, PSXRecomp-Framework, ca. 400 MB). Danach dauert jedes
   Spiel etwa 5–15 Minuten.
3. In der Bibliothek auf **Spielen** klicken.

Daten liegen unter `%LOCALAPPDATA%\SpyroTrilogy`.

## Selbst paketieren (Windows)

Voraussetzung: Python 3.11–3.13 (nicht 3.14, wegen pythonnet).

```powershell
powershell -ExecutionPolicy Bypass -File .\PAKETIEREN.ps1            # EXE + ZIP in dist\
powershell -ExecutionPolicy Bypass -File .\PAKETIEREN.ps1 -NurStarten # direkt starten
```

## Aufbau

| Pfad | Inhalt |
|---|---|
| `app.py` | Fenster (pywebview/WebView2), Entwicklungsserver mit `--serve` |
| `backend/` | Disc-Prüfung, Bauablauf, Einstellungen, Steuerung, Framework-Patches |
| `ui/` | Oberfläche (HTML/CSS/JS), Übersetzungen, Schriften |
| `kits/spyro1-3/` | Projektdateien je Spiel (ohne generierten Code), Spielmenü, Fixes |
| `kits/common/` | gemeinsame Quelle des Spielmenüs (`spyro_menu*.cpp`) |

## Lizenzen und Hinweise

- PSXRecomp steht unter der **PolyForm Noncommercial License 1.0.0**; die App
  lädt es beim ersten Start herunter, sie enthält es nicht. Damit gebaute
  Spiele dürfen nicht kommerziell genutzt werden.
- recomp-ui: MIT-Lizenz.
- Schriften: Fredoka und Atkinson Hyperlegible, SIL Open Font License 1.1
  (Lizenztexte in `ui/fonts/` und `kits/*/assets/spyro/`).
- Inoffizielles Fanprojekt, nicht verbunden mit Sony Interactive
  Entertainment, Insomniac Games, Toys for Bob oder Activision. „Spyro“ ist
  eine Marke ihrer jeweiligen Inhaber.

---

## English summary

Spyro Trilogy is a Windows app that turns **your own** PAL disc images of the
three PlayStation Spyro games into native PC games via static recompilation
(PSXRecomp) – no emulation. It ships no game data or code; everything is built
locally from your images. It offers guided setup with disc verification, a
library to launch and configure each game (resolution up to 8×, AA, PGXP,
CRT filter, key and controller bindings), an in-game menu, and German/English
UI. PSXRecomp is PolyForm Noncommercial; this is an unofficial fan project.
