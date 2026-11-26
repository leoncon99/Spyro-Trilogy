/* spyro3_fixes.c -- fixes for Spyro: Year of the Dragon (PAL, SCES-02835).
 *
 * Loading-screen flicker
 * ----------------------
 * During loading screens the PAL build calls PutDispEnv (0x8005CBBC, PsyQ
 * libgpu) on alternate frames with a DISPENV whose screen.h is 0. libgpu
 * then falls back to its NTSC default of 240 lines, so GP1(07h) toggles the
 * vertical display range between 256 lines (39..295) and 240 lines (39..279)
 * every other frame.
 *
 * On a CRT only the bottom 16 border lines blink. The port scales the
 * displayed range to the window, so the whole picture jumped in size.
 *
 * Fix: a pre-hook on PutDispEnv. When a 256-line PAL buffer (disp.h == 256)
 * arrives with screen.h == 0, write 256 into the guest DISPENV, then let the
 * original function run unchanged (the hook declines). All state stays in
 * guest RAM, so replays and save states remain deterministic.
 *
 * DISPENV layout: RECT disp {x,y,w,h} at +0, RECT screen {x,y,w,h} at +8,
 * u8 isinter, isrgb24, pad0, pad1 at +16.
 */
#include <stdint.h>
#include "func_override.h"
#include "cpu_state.h"

uint16_t psx_read_half(uint32_t addr);

#define SPYRO3_PUTDISPENV 0x8005CBBCu

static int spyro3_putdispenv_prehook(struct CPUState *cpu) {
    const uint32_t env = cpu->gpr[4];
    if (env) {
        const uint16_t disp_h = psx_read_half(env + 6);
        const uint16_t screen_h = psx_read_half(env + 14);
        if (disp_h == 256 && screen_h == 0)
            psx_write_half(env + 14, 256);
    }
    return 0; /* decline: the original PutDispEnv runs */
}

__attribute__((constructor)) static void spyro3_register_fixes(void) {
    /* addiu sp,sp,-32 ; sw s1,20(sp) -- the PAL PutDispEnv prologue */
    static const uint32_t guard[2] = {0x27BDFFE0u, 0xAFB10014u};
    func_override_add_guarded("spyro3.pal_loading_screen_height",
                              SPYRO3_PUTDISPENV, spyro3_putdispenv_prehook,
                              guard, 2, 0);
}
