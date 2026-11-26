/* spyro_menu.cpp -- full in-game menu for the Spyro PAL ports.
 *
 * psxrecomp only attaches recomp-ui's in-game menu by default for multi-disc
 * titles; single-disc games get the small fallback menu (fullscreen, window
 * size, volume, resume). Registering the provider explicitly gives every
 * Spyro port the complete menu: display and graphics settings (internal
 * resolution, anti-aliasing, texture filtering, PGXP, ...), restart game,
 * return to launcher and quit.
 *
 * Opens with F10 / Ctrl+L, or Select + L3 on a controller.
 */
#include "psx_menu_host.h"

#if defined(RECOMP_LAUNCHER) && defined(__has_include)
#if __has_include("recomp_ui_psx_menu.h")
#include "recomp_ui_psx_menu.h"

namespace {
struct SpyroMenuRegistration {
    SpyroMenuRegistration() { psx_menu_set_provider(recomp_ui_psx_menu_provider()); }
};
const SpyroMenuRegistration g_spyro_menu_registration;
}  // namespace

#endif
#endif
