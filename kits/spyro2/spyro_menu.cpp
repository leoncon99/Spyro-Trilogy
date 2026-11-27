/* spyro_menu.cpp -- in-game menu for the Spyro Trilogy ports.
 *
 * 1. Registers recomp-ui's full in-game menu (psxrecomp only attaches it by
 *    default for multi-disc titles).
 * 2. Leaving the game returns to Spyro Trilogy (still open behind the game),
 *    never to the framework's own launcher.
 * 3. Translates the menu. Language: SPYRO_LANG (set by Spyro Trilogy), else
 *    the system UI language, else English. Needs the Spyro framework patch
 *    that adds recomp_runtime_ui_translate.
 *
 * 4. Draws the menu in the app's style (spyro_menu_ui.cpp).
 *
 * Opens with F10 / Ctrl+L, or Select + L3 on a controller.
 */
#include "psx_menu_host.h"
#if __has_include("savestate.h")
#include "savestate.h"
#define SPYRO_HAS_SAVESTATE 1
#endif

#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>
#include <unordered_map>

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#endif

#if defined(RECOMP_LAUNCHER) && defined(__has_include)
#if __has_include("recomp_ui_psx_menu.h")
#include "recomp_ui_psx_menu.h"
#define SPYRO_HAS_MENU 1
#endif
#endif

extern "C" const char *(*recomp_runtime_ui_translate)(const char *);
void spyro_menu_ui_install(const char *assets_dir);  // spyro_menu_ui.cpp

namespace {

/* ---------------------------------------------------------------- language */
struct Entry { const char *en; const char *de; };

/* English source text -> German. Entries whose German is nullptr only exist
 * to override the English wording (see kEnglish below). */
const Entry kGerman[] = {
    {"Game menu", "Spielmenü"},
    {"Paused", "Pausiert"},
    {"Settings", "Einstellungen"},
    {"Resume", "Weiter"},
    {"Select", "Auswählen"},
    {"Open", "Öffnen"},
    {"Change", "Ändern"},
    {"Back", "Zurück"},
    {"< Back", "< Zurück"},
    {"Navigate", "Navigieren"},
    {"D-pad / Arrows", "Steuerkreuz / Pfeiltasten"},
    {"Enter / Cross", "Enter / Kreuz"},
    {"Esc / Circle", "Esc / Kreis"},
    {"Tap a section or setting", "Bereich oder Einstellung antippen"},
    {"OPEN", "\u203A"},
    {"(not set)", "(nicht gesetzt)"},
    {"Unavailable", "Nicht verfügbar"},
    {"On", "An"},
    {"Off", "Aus"},
    {"Applied", "Übernommen"},
    {"Done", "Erledigt"},
    {"Saved", "Gespeichert"},
    {"Close", "Schließen"},
    {"Up", "Hoch"},
    {"Down", "Runter"},
    {"Press again to confirm", "Zum Bestätigen erneut drücken"},
    {"UP/DOWN SELECT  LEFT/RIGHT CHANGE  ENTER ACCEPT", "HOCH/RUNTER WÄHLEN  LINKS/RECHTS ÄNDERN  ENTER OK"},
    {"ENTER OPEN  ESC BACK", "ENTER ÖFFNEN  ESC ZURÜCK"},

    {"Display", "Anzeige"},
    {"Graphics", "Grafik"},
    {"Audio", "Ton"},
    {"System", "Spiel"},
    {"Input", "Eingabe"},
    {"Disc", "Disc"},

    {"Fullscreen", "Vollbild"},
    {"Choose windowed or fullscreen output.", "Fenster oder Vollbild."},
    {"Windowed", "Fenster"},
    {"Borderless", "Randlos"},
    {"Exclusive", "Exklusiv"},
    {"Window scale", "Fenstergröße"},
    {"Resize the window in native-size steps.", "Fenstergröße in Vielfachen der Originalauflösung."},
    {"View mode", "Bildformat"},
    {"Native, fixed widescreen, or live window aspect.", "Original, festes Breitbild oder wie das Fenster."},
    {"Native", "Original"},
    {"16:9 fixed", "16:9 fest"},
    {"Adaptive", "Adaptiv"},
    {"Edge HUD", "HUD am Rand"},
    {"Anchor status groups to widescreen edges.", "Anzeigen an den Breitbild-Rand verschieben."},
    {"Game dimming", "Spiel abdunkeln"},
    {"How dark the game gets behind a menu.", "Wie dunkel das Spiel hinter dem Menü wird."},
    {"Menu opacity", "Menü-Deckkraft"},
    {"How solid the menus' backgrounds are.", "Wie undurchsichtig der Menühintergrund ist."},
    {"Integer scaling", "Ganzzahlige Skalierung"},
    {"Snap output to whole native-pixel multiples.", "Bild nur in ganzen Vielfachen vergrößern."},
    {"Linear filter", "Linearer Filter"},
    {"Smooth the final game image.", "Fertiges Bild glätten."},
    {"Texture filtering", "Texturfilter"},
    {"Choose nearest or linear sampling.", "Scharf oder weich filtern."},
    {"FMV filtering", "Video-Filter"},
    {"Choose how full-motion video is scaled up.", "Wie Videosequenzen vergrößert werden."},
    {"Resolution scale", "Auflösungsfaktor"},
    {"Set the internal rendering resolution.", "Interne Berechnungsauflösung."},
    {"Enable or mute game audio output.", "Ton an- oder ausschalten."},
    {"Volume", "Lautstärke"},
    {"Set the in-game mixer volume.", "Lautstärke im Spiel."},

    {"Resume game", "Weiterspielen"},
    {"Close settings and return to the game.", "Menü schließen und weiterspielen."},
    {"State slot", "Speicherplatz"},
    {"The slot Save state and Load state use.", "Platz für Schnellspeichern und -laden."},
    {"Save state", "Schnellspeichern"},
    {"Save the current state.", "Aktuellen Spielstand sofort speichern."},
    {"Load state", "Schnellladen"},
    {"Load the current state slot.", "Spielstand aus dem gewählten Platz laden."},
    {"Pause in menu", "Pause im Menü"},
    {"Hold the game while a menu is open.", "Spiel anhalten, solange das Menü offen ist."},
    {"Reset game", "Spiel zurücksetzen"},
    {"Reset the emulated machine.", "Die Konsole zurücksetzen."},
    {"Return to launcher", "Zurück zur Bibliothek"},
    {"Close the game, open the launcher. Press twice.",
     "Spiel beenden und zurück zu Spyro Trilogy. Zweimal drücken."},
    {"Press again for the launcher", "Erneut drücken, um zur Bibliothek zurückzukehren"},
    {"Quit game", "Spiel beenden"},
    {"Close the game. Press twice.", "Spiel schließen und zurück zu Spyro Trilogy. Zweimal drücken."},
    {"Press again to quit", "Zum Beenden erneut drücken"},
    {"Restart game", "Spiel neu starten"},
    {"Reset the console: the game starts again from its boot screen. Unsaved progress is lost.",
     "Konsole neu starten: Das Spiel beginnt wieder beim Startbildschirm. Nicht gespeicherter Fortschritt geht verloren."},
    {"Press again to restart the game. Unsaved progress is lost.",
     "Erneut drücken, um neu zu starten. Nicht gespeicherter Fortschritt geht verloren."},
    {"Restart is unavailable online.", "Neustart ist online nicht möglich."},
    {"Restart is unavailable in this game mode.", "Neustart ist in diesem Modus nicht möglich."},

    {"Renderer", "Grafikausgabe"},
    {"Applies with a restart when the menu closes.", "Gilt nach einem Neustart beim Schließen des Menüs."},
    {"Software", "Software"},
    {"Render thread", "Render-Thread"},
    {"Use a second CPU thread for OpenGL; restarts when this menu closes.",
     "Zweiter CPU-Thread für OpenGL; Neustart beim Schließen des Menüs."},
    {"Present thread", "Ausgabe-Thread"},
    {"Present OpenGL frames on another thread. Requires Render thread; restarts when this menu closes.",
     "Bilder auf eigenem Thread ausgeben. Braucht den Render-Thread; Neustart beim Schließen."},
    {"VSync", "VSync"},
    {"Driver synchronization and variable-refresh presentation.", "Bildsynchronisation gegen Bildrisse."},
    {"Internal resolution", "Interne Auflösung"},
    {"Render the 3D picture at a higher scale. Higher is sharper and uses more GPU.",
     "Wie scharf die 3D-Welt berechnet wird. Höher = schärfer, braucht mehr Grafikleistung."},
    {"1x (Native)", "1× (Original)"},
    {"PGXP precision", "Wackel-Korrektur (PGXP)"},
    {"Steadier 3D: polygons stop wobbling and textures stop warping. Applies with a quick restart.",
     "Ruhigere 3D-Grafik ohne wackelnde Polygone und verzerrte Texturen. Gilt nach kurzem Neustart."},
    {"Antialiasing", "Kantenglättung"},
    {"Smooth jagged edges of the finished picture.", "Glättet treppenartige Kanten."},
    {"FXAA (high quality)", "FXAA (hohe Qualität)"},
    {"CRT filter", "Röhrenfernseher-Filter"},
    {"A period TV look (colour and scanlines). Applies with a quick restart.",
     "Bild wie auf einem alten Fernseher. Gilt nach kurzem Neustart."},
    {"Scanlines", "Scanlines"},
    {"Dark gaps between display lines, like a CRT. Uses the CRT filter.",
     "Dunkle Zeilen wie bei alten Fernsehern. Nutzt den Röhrenfilter."},
    {"Smoothing", "Glättung"},
    {"How the picture is scaled to the window: Smooth blends pixels, Sharp keeps hard edges.",
     "Wie das Bild ans Fenster angepasst wird: Weich mischt Pixel, Scharf behält harte Kanten."},
    {"Game default", "Spiel-Standard"},
    {"Smooth", "Weich"},
    {"Sharp", "Scharf"},
    {"Nearest", "Scharf"},
    {"Linear", "Linear"},
    {"Bilinear", "Bilinear"},
    {"Bicubic", "Bikubisch"},
    {"Nearest is the console's look; Bilinear softens; xBR rounds pixel-art edges.",
     "Scharf wie die Konsole; Bilinear weich; xBR rundet Pixelkanten."},
    {"Dithering", "Dithering"},
    {"The console's dither pattern. Off shows true colour; Fine dithers at the internal resolution.",
     "Das Punktmuster der Konsole. Aus zeigt echte Farben; Fein rastert in hoher Auflösung."},
    {"Off (true colour)", "Aus (echte Farben)"},
    {"Console", "Wie Konsole"},
    {"Fine", "Fein"},
    {"Applies after the match", "Gilt nach dem Match"},
    {"Applies with a quick restart when you close the menu",
     "Wird beim Schließen übernommen: Das Spiel lädt kurz neu und macht genau hier weiter."},
    {"Unavailable online", "Online nicht verfügbar"},
    {"Online: the game keeps running", "Online: Das Spiel läuft weiter"},

    {"Controller 1 port", "Anschluss Controller 1"},
    {"Move controller 1 to console port 2 or back, as if the plug were moved. Some games ask for it.",
     "Controller 1 an Anschluss 2 umstecken oder zurück. Manche Spiele verlangen das."},
    {"Port 1", "Anschluss 1"},
    {"Port 2", "Anschluss 2"},
    {"Selected disc", "Gewählte Disc"},
    {"Choose a disc, then Insert disc and resume.", "Disc wählen, dann „Disc einlegen“."},
    {"Insert disc and resume", "Disc einlegen und weiter"},
    {"Change the disc while the game keeps running.", "Disc wechseln, während das Spiel läuft."},
    {"Reinsert current disc", "Disc neu einlegen"},
    {"Open and close the lid with the same disc.", "Deckel mit derselben Disc öffnen und schließen."},
    {"Disc changes are unavailable in this game mode.", "Disc-Wechsel ist in diesem Modus nicht möglich."},
    {"That disc could not be inserted.", "Die Disc konnte nicht eingelegt werden."},
};

/* English wording that differs from the framework's (launcher -> library). */
const Entry kEnglish[] = {
    {"OPEN", "\u203A"},
    {"Return to launcher", "Back to library"},
    {"Close the game, open the launcher. Press twice.", "Quit the game and return to Spyro Trilogy. Press twice."},
    {"Press again for the launcher", "Press again to return to the library"},
    {"System", "Game"},
    {"Applies with a quick restart when you close the menu",
     "Applies when you close the menu: the game reloads briefly and continues right here."},
    /* identity: lets a status line cut at 48 bytes be found by its start */
    {"Press again to restart the game. Unsaved progress is lost.",
     "Press again to restart the game. Unsaved progress is lost."},
    {"Press again to return to the library", "Press again to return to the library"},
    {"Close the game. Press twice.", "Quit the game and return to Spyro Trilogy. Press twice."},
};

std::unordered_map<std::string, const char *> g_table;

const char *translate(const char *s) {
    auto it = g_table.find(s);
    if (it != g_table.end()) return it->second;
    /* The menu keeps status lines in 48 bytes: match a cut-off line by its start. */
    const size_t n = std::strlen(s);
    if (n >= 40) {
        for (const auto &e : g_table)
            if (e.first.size() > n && e.first.compare(0, n, s) == 0) return e.second;
    }
    return s;
}

std::string detect_language() {
    if (const char *env = std::getenv("SPYRO_LANG"))
        if (env[0]) return std::string(env).substr(0, 2);
#if defined(_WIN32)
    const LANGID id = GetUserDefaultUILanguage();
    if (PRIMARYLANGID(id) == LANG_GERMAN) return "de";
#else
    if (const char *l = std::getenv("LANG"))
        if (std::strncmp(l, "de", 2) == 0) return "de";
#endif
    return "en";
}

void install_translator() {
    if (detect_language() == "de") {
        for (const Entry &e : kGerman) g_table[e.en] = e.de;
    } else {
        for (const Entry &e : kEnglish) g_table[e.en] = e.de;
    }
    recomp_runtime_ui_translate = translate;
}

/* ---------------------------------------------------------------- provider */
#if defined(SPYRO_HAS_MENU)
PsxMenuProvider g_provider;      // recomp-ui's provider with our attach
const PsxMenuProvider *g_inner;  // recomp-ui's original
PsxMenuHost g_host;              // the runtime's host with our exit policy
void (*g_inner_exit)(int);
int (*g_inner_session_set)(int, int);
std::atomic<bool> g_cold_restart{false};  // "Restart game": a real reset
std::atomic<bool> g_resume_busy{false};

void set_env(const char *name, const char *value) {
#if defined(_WIN32)
    _putenv_s(name, value ? value : "");
#else
    if (value) setenv(name, value, 1); else unsetenv(name);
#endif
}

int spyro_session_set(int setting, int value) {
    const int rc = g_inner_session_set ? g_inner_session_set(setting, value) : 0;
#if defined(PSX_MENU_HOST_HAS_LOOK_ROWS)
    if (rc && setting == PSX_MENU_SESSION_RESTART_GAME && value == 1) g_cold_restart = true;
#endif
    return rc;
}

#if defined(SPYRO_HAS_SAVESTATE)
/* A settings change that needs a restart: save the game to a reserved state
 * slot, then restart into that state, so the player continues exactly where
 * the menu was closed instead of at the boot screen. If saving fails, the
 * restart happens as before. */
constexpr int kResumeSlot = SAVESTATE_SLOTS - 1;
void restart_with_resume() {
    PSXSavestateStatus before{};
    savestate_get_status(&before);
    (void)savestate_take_save_failed();
    char slot[8];
    std::snprintf(slot, sizeof slot, "%d", kResumeSlot);
    set_env("PSX_LOAD_SLOT", slot);              // read by the restarted game
    if (!savestate_request_save(kResumeSlot)) {
        set_env("PSX_LOAD_SLOT", nullptr);
        g_inner_exit(PSX_MENU_EXIT_RELAUNCH);
        return;
    }
    g_resume_busy = true;
    std::thread([before]() {
        bool ok = false;
        for (int i = 0; i < 300; ++i) {          // the game saves within a frame or two
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            if (savestate_take_save_failed()) break;
            PSXSavestateStatus s{};
            savestate_get_status(&s);
            if (s.generation != before.generation && !s.pending) {
                ok = s.last_ok && s.last_slot == kResumeSlot;
                break;
            }
        }
        if (!ok) set_env("PSX_LOAD_SLOT", nullptr);
        std::fprintf(stdout, "spyro: settings restart %s\n", ok ? "resumes from a save state" : "without a save state");
        std::fflush(stdout);
        g_resume_busy = false;
        g_inner_exit(PSX_MENU_EXIT_RELAUNCH);
    }).detach();
}
#endif

void spyro_request_exit(int how) {
    /* Spyro Trilogy is the launcher: leaving the game returns to it. */
    if (how == PSX_MENU_EXIT_TO_FRONTEND) how = PSX_MENU_EXIT_QUIT;
    if (how == PSX_MENU_EXIT_RELAUNCH) {
        if (g_cold_restart.exchange(false)) {
            set_env("PSX_LOAD_SLOT", nullptr);       // "Restart game" boots fresh
        } else {
#if defined(SPYRO_HAS_SAVESTATE)
            if (g_resume_busy) return;
            restart_with_resume();
            return;
#endif
        }
    }
    if (g_inner_exit) g_inner_exit(how);
}

int spyro_attach(void *ctx, void *window, void *gl, const PsxMenuHost *host) {
    if (!host) return g_inner->attach(ctx, window, gl, host);
    /* Our look and fonts (staged into assets/spyro by the game's CMakeLists.txt) */
    spyro_menu_ui_install(host->assets_dir);
    g_host = *host;
    g_inner_exit = host->request_exit;
    g_host.request_exit = spyro_request_exit;
    g_inner_session_set = host->session_set;
    if (host->session_set) g_host.session_set = spyro_session_set;
    return g_inner->attach(ctx, window, gl, &g_host);
}

struct Registration {
    Registration() {
        install_translator();
        g_inner = recomp_ui_psx_menu_provider();
        if (!g_inner) return;
        g_provider = *g_inner;
        g_provider.attach = spyro_attach;
        psx_menu_set_provider(&g_provider);
    }
};
const Registration g_registration;
#else
struct Registration {
    Registration() { install_translator(); }
};
const Registration g_registration;
#endif

}  // namespace
