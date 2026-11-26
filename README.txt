Spyro Trilogy - native PC ports of the PlayStation Spyro games
==============================================================

This program builds native PC games from YOUR OWN Spyro discs and launches
them. It contains no game data and does not download any.

Supported (PAL/Europe):
  - Spyro the Dragon              (SCES-01438)
  - Spyro 2: Gateway to Glimmer   (SCES-02104, with .sbi file)
  - Spyro: Year of the Dragon     (SCES-02835, with .sbi file)

How it works
------------
1. Create images of your discs in .cue + .bin format (e.g. with DuckStation,
   ImgBurn or a Redump tool). For Spyro 2 and 3 you also need the matching
   .sbi file (copy protection data) with the same name next to the .cue.
2. Run "Spyro Trilogy.exe" and choose "Start setup".
3. Choose the images (or the folder that holds them) and click "Build games".
   The first time, the tools are downloaded once (Python, compiler,
   framework - about 400 MB). After that each game takes about 5-15 minutes.
4. Done: click "Play" in the library.

In game
-------
  Menu (settings, quit):  F10  or  Ctrl+L  or controller Select + L3
  Toggle fullscreen:      Alt+Enter

Locations
---------
  Everything lives in  %LOCALAPPDATA%\SpyroTrilogy
  Saves:               ...\games\<game>\project\build-release\saves
  Build log:           ...\games\<game>\build.log

Technology
----------
Static recompilation with PSXRecomp (github.com/mstan/psxrecomp) and
recomp-ui. Fonts: Fredoka and Atkinson Hyperlegible (SIL OFL 1.1).
Licence: PolyForm Noncommercial 1.0.0 - no commercial use.
Unofficial fan project, not affiliated with Sony, Insomniac or Activision.
Source: https://github.com/leoncon99/Spyro-PAL-Triology
