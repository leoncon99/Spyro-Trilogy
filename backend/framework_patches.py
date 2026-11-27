"""Small, verified edits to the downloaded framework.

Each patch is (relative path, exact old text, new text). A patch whose new
text is already present is skipped; a patch whose old text is missing stops
the setup with a clear error instead of building something half-patched.
"""
from __future__ import annotations

from pathlib import Path

PATCH_LEVEL = "spyro-patches-6"

_RT = "recomp-ui/src/common/backends/imgui/runtime_ui_imgui.cpp"

# In-game menu: route every visible string through an optional translator that
# the game sets (spyro_menu.cpp). Without a translator nothing changes.
PATCHES: list[tuple[str, str, str]] = [
    (_RT, '#include <cstring>\n\nnamespace {\n',
     '#include <cstring>\n\n'
     'extern "C" {\n'
     '/* Optional translator for the in-game menu (set by the game). */\n'
     'const char *(*recomp_runtime_ui_translate)(const char *) = nullptr;\n'
     '/* Optional TTF for the in-game menu (set by the game); size in pixels. */\n'
     'const char *recomp_runtime_ui_font_path = nullptr;\n'
     'float recomp_runtime_ui_font_size = 18.0f;\n'
     '}\n'
     'static const char *TR(const char *s) {\n'
     '    return (s && recomp_runtime_ui_translate) ? recomp_runtime_ui_translate(s) : s;\n'
     '}\n\n'
     'namespace {\n'),
    (_RT, 'std::snprintf(out, out_size, "OPEN");', 'std::snprintf(out, out_size, "%s", TR("OPEN"));'),
    (_RT, 'std::snprintf(out, out_size, "%s", buf[0] ? buf : "(not set)");',
     'std::snprintf(out, out_size, "%s", buf[0] ? buf : TR("(not set)"));'),
    (_RT, '''    if (!recomp_runtime_ui_current_value(ui, item, &value)) {
        std::snprintf(out, out_size, "Unavailable");''',
     '''    if (!recomp_runtime_ui_current_value(ui, item, &value)) {
        std::snprintf(out, out_size, "%s", TR("Unavailable"));'''),
    (_RT, 'std::snprintf(out, out_size, "%s", value ? "On" : "Off");',
     'std::snprintf(out, out_size, "%s", TR(value ? "On" : "Off"));'),
    (_RT, '''            std::snprintf(out, out_size, "%s", item->choices[index]);
        else
            std::snprintf(out, out_size, "Unavailable");''',
     '''            std::snprintf(out, out_size, "%s", TR(item->choices[index]));
        else
            std::snprintf(out, out_size, "%s", TR("Unavailable"));'''),
    (_RT, 'ImGui::Selectable(ui->sections[index], selected,', 'ImGui::Selectable(TR(ui->sections[index]), selected,'),
    (_RT, 'ImGui::CalcTextSize(item->description, nullptr, false,',
     'ImGui::CalcTextSize(TR(item->description), nullptr, false,'),
    (_RT, 'label_color, item->label ? item->label : "");', 'label_color, item->label ? TR(item->label) : "");'),
    (_RT, 'u32(theme.text_muted), item->description, nullptr,', 'u32(theme.text_muted), TR(item->description), nullptr,'),
    (_RT, 'ImGui::TextUnformatted(ui->config.title ? ui->config.title : "Settings");',
     'ImGui::TextUnformatted(TR(ui->config.title ? ui->config.title : "Settings"));'),
    (_RT, 'const float subtitle_w = ImGui::CalcTextSize(ui->config.subtitle).x;',
     'const float subtitle_w = ImGui::CalcTextSize(TR(ui->config.subtitle)).x;'),
    (_RT, 'ImGui::TextDisabled("%s", ui->config.subtitle);', 'ImGui::TextDisabled("%s", TR(ui->config.subtitle));'),
    (_RT, 'const char *close_label = "Resume";', 'const char *close_label = TR("Resume");'),
    (_RT, 'std::snprintf(hint, sizeof hint, "Tap a section or setting");',
     'std::snprintf(hint, sizeof hint, "%s", TR("Tap a section or setting"));'),
    (_RT, '''            std::snprintf(hint, sizeof hint, "%s  Select    %s  Back    D-pad / Arrows  Navigate",
                ui->config.accept_label ? ui->config.accept_label : "Select",
                ui->config.back_label ? ui->config.back_label : "Back");''',
     '''            std::snprintf(hint, sizeof hint, "%s  %s    %s  %s    %s  %s",
                TR(ui->config.accept_label ? ui->config.accept_label : "Enter / Cross"), TR("Select"),
                TR(ui->config.back_label ? ui->config.back_label : "Esc / Circle"), TR("Back"),
                TR("D-pad / Arrows"), TR("Navigate"));'''),
    (_RT, 'ImGui::CalcTextSize(ui->status, nullptr, false, text_w).y;',
     'ImGui::CalcTextSize(TR(ui->status), nullptr, false, text_w).y;'),
    (_RT, 'ImGui::TextUnformatted(ui->status);', 'ImGui::TextUnformatted(TR(ui->status));'),
    (_RT, 'if (ImGui::SmallButton("< Back")) recomp_runtime_ui_leave_folder(ui);',
     'if (ImGui::SmallButton(TR("< Back"))) recomp_runtime_ui_leave_folder(ui);'),
    (_RT, 'if (ImGui::SmallButton("< Back") &&', 'if (ImGui::SmallButton(TR("< Back")) &&'),
    (_RT, '''            ImGui::PushStyleColor(ImGuiCol_Text, col(theme.accent2));
            ImGui::TextUnformatted(page_title);''',
     '''            ImGui::PushStyleColor(ImGuiCol_Text, col(theme.accent2));
            ImGui::TextUnformatted(TR(page_title));'''),
    (_RT, '''                recomp_runtime_ui_page_title(ui, page_title, sizeof(page_title));
                ImGui::TextUnformatted(page_title);''',
     '''                recomp_runtime_ui_page_title(ui, page_title, sizeof(page_title));
                ImGui::TextUnformatted(TR(page_title));'''),
    (_RT, 'ImGui::TextUnformatted(ui->toast_title);', 'ImGui::TextUnformatted(TR(ui->toast_title));'),
    (_RT, 'ImGui::TextUnformatted(ui->toast_body);', 'ImGui::TextUnformatted(TR(ui->toast_body));'),
]


_PROV = "recomp-ui/src/consoles/psx/psx_menu_provider_imgui.cpp"

# In-game menu: load the game's font instead of ImGui's built-in bitmap font.
PATCHES += [
    (_PROV, 'void draw(int w, int h) {\n',
     'extern "C" const char *recomp_runtime_ui_font_path;\n'
     'extern "C" float recomp_runtime_ui_font_size;\n\n'
     'void draw(int w, int h) {\n'),
    (_PROV,
     '        g_ctx = ImGui::CreateContext();\n'
     '        ImGui::SetCurrentContext(g_ctx);\n'
     '        ImGui::GetIO().IniFilename = nullptr;\n',
     '        g_ctx = ImGui::CreateContext();\n'
     '        ImGui::SetCurrentContext(g_ctx);\n'
     '        ImGui::GetIO().IniFilename = nullptr;\n'
     '        if (recomp_runtime_ui_font_path && recomp_runtime_ui_font_path[0]) {\n'
     '            /* Latin-1, punctuation incl. German quotes, arrows, shapes */\n'
     '            static const ImWchar ranges[] = {0x0020, 0x00FF, 0x2010, 0x2027, 0x2190, 0x21FF,\n'
     '                                             0x25A0, 0x25FF, 0};\n'
     '            ImGui::GetIO().Fonts->AddFontFromFileTTF(recomp_runtime_ui_font_path,\n'
     '                                                     recomp_runtime_ui_font_size, nullptr, ranges);\n'
     '        }\n'),
]

# Level 3: include U+2028..U+203A (e.g. the › used for actions).
PATCHES += [
    (_PROV, '0x2010, 0x2027, 0x2190', '0x2010, 0x203A, 0x2190'),
]

# Level 4: the game draws the whole in-game menu itself (spyro_menu.cpp, in the
# app's style) and loads its own fonts; the provider remembers whether the
# player last used a keyboard or a controller. "Return to launcher" goes: in
# Spyro Recomp Trilogy it would do exactly what "Quit game" does.
_PSXPROV = "recomp-ui/src/consoles/psx/psx_menu_provider.cpp"
PATCHES += [
    (_RT, 'float recomp_runtime_ui_font_size = 18.0f;\n}\n',
     'float recomp_runtime_ui_font_size = 18.0f;\n'
     '/* Optional: the game draws the menu itself / loads its fonts (before NewFrame). */\n'
     'void (*recomp_runtime_ui_custom_render)(RecompRuntimeUi *) = nullptr;\n'
     'void (*recomp_runtime_ui_fonts_hook)(int, int) = nullptr;\n'
     '/* 1 when the player last pressed a controller button, 0 for the keyboard. */\n'
     'int recomp_runtime_ui_last_input_pad = 0;\n'
     '}\n'),
    (_RT, 'extern "C" void recomp_runtime_ui_render_imgui(RecompRuntimeUi *ui) {\n'
          '    if (!ui || ImGui::GetCurrentContext() == nullptr) return;\n',
     'extern "C" void recomp_runtime_ui_render_imgui(RecompRuntimeUi *ui) {\n'
     '    if (!ui || ImGui::GetCurrentContext() == nullptr) return;\n'
     '    if (recomp_runtime_ui_custom_render) { recomp_runtime_ui_custom_render(ui); return; }\n'),
    (_PROV, 'extern "C" float recomp_runtime_ui_font_size;\n\nvoid draw(',
     'extern "C" float recomp_runtime_ui_font_size;\n'
     'extern "C" void (*recomp_runtime_ui_fonts_hook)(int, int);\n\n'
     'void draw('),
    (_PROV, '    ImGui::SetCurrentContext(g_ctx);\n    if (!g_gl_ready) g_gl_ready',
     '    ImGui::SetCurrentContext(g_ctx);\n'
     '    if (recomp_runtime_ui_fonts_hook) recomp_runtime_ui_fonts_hook(w, h);\n'
     '    if (!g_gl_ready) g_gl_ready'),
    (_PROV, '}  // namespace\n\nint sdl_event(const void *p) {\n',
     '}  // namespace\n\n'
     'extern "C" int recomp_runtime_ui_last_input_pad;\n\n'
     'int sdl_event(const void *p) {\n'),
    (_PROV, '    if (e.type == SDL_EVENT_KEY_DOWN) {\n        const SDL_Keycode k = e.key.key;\n',
     '    if (e.type == SDL_EVENT_KEY_DOWN) {\n        recomp_runtime_ui_last_input_pad = 0;\n'
     '        const SDL_Keycode k = e.key.key;\n'),
    (_PROV, '        const unsigned bit = 1u << e.gbutton.button;\n',
     '        if (e.type == SDL_EVENT_GAMEPAD_BUTTON_DOWN) recomp_runtime_ui_last_input_pad = 1;\n'
     '        const unsigned bit = 1u << e.gbutton.button;\n'),
    (_PSXPROV, 'RECOMP_RUNTIME_UI_STANDARD_RESUME | RECOMP_RUNTIME_UI_STANDARD_RETURN_TO_LAUNCHER |\n'
               '                   RECOMP_RUNTIME_UI_STANDARD_QUIT;',
     'RECOMP_RUNTIME_UI_STANDARD_RESUME | RECOMP_RUNTIME_UI_STANDARD_QUIT;'),
]


# Level 5: real PAL frame timing. The runtime ran PAL VBlank at exactly
# 50.00 Hz (677376 CPU cycles); a real PAL PS1 runs 314 lines of 3406 dots at
# 53.203425 MHz = 680823 CPU cycles (49.75 Hz). SPU and CD-ROM run on the CPU
# clock, so VBlank was 0.5 % fast against them. Spyro 2 streams cutscene
# speech into a two-half SPU ring and refills it on a VBlank schedule: the
# 0.5 % drift made the refills overtake playback after about a minute
# (rushed or repeated words, then silence). Host pacing follows the same
# rate. NTSC timing is unchanged.
_VT = "psxrecomp/runtime/include/psx_video_timing.h"
_MAIN = "psxrecomp/runtime/src/main.cpp"
PATCHES += [
    (_VT, '#define PSX_VBLANK_CYCLES_PAL    677376u  /* 33.8688 MHz / 50 Hz */',
     '#define PSX_VBLANK_CYCLES_PAL    680823u  /* real PAL: 314 x 3406 dots @ 53.203425 MHz = 49.75 Hz */'),
    (_MAIN, '    return psx_video_timing_is_pal() ? 50.0 : 1000.0 / PSX_FRAME_PERIOD_MS;',
     '    return psx_video_timing_is_pal() ? 33868800.0 / PSX_VBLANK_CYCLES_PAL\n'
     '                                     : 1000.0 / PSX_FRAME_PERIOD_MS;'),
    (_MAIN, '        ? 1000.0 / 50.0\n        : PSX_FRAME_PERIOD_MS;',
     '        ? 1000.0 * PSX_VBLANK_CYCLES_PAL / 33868800.0\n        : PSX_FRAME_PERIOD_MS;'),
]

# Level 6: the in-game menu's look rows (internal resolution, PGXP, CRT filter,
# scanlines, smoothing, texture filtering) still pointed at the built-in
# "setting mods" the framework retired into settings.toml, so they all showed
# "unavailable". They now read and write the player settings: internal
# resolution applies live, the others are saved and apply with the quick
# restart when the menu closes (as the framework intends for these rows).
_L6_ROWS_OLD = """        {kOvlIresPkg, "internal-resolution", "resolution", kOvlIres, 7},
        {kOvlPgxp, "pgxp", nullptr, nullptr, 2},
        {kOvlCrt, "crt-filter", nullptr, nullptr, 2},
        {nullptr, nullptr, nullptr, nullptr, 3},  /* antialiasing: runtime */
        {kOvlCrt, "crt-filter", "scanlines", kOvlOnOff, 2},
        {kOvlImage, "image-filtering", "smoothing", kOvlSmooth, 3},
        {kOvlImage, "image-filtering", "texture_filtering", kOvlTexture, 4},"""
_L6_ROWS_NEW = """        /* Spyro Trilogy: all player settings now (spyro_look_get/set). */
        {nullptr, nullptr, nullptr, kOvlIres, 7},
        {nullptr, nullptr, nullptr, nullptr, 2},
        {nullptr, nullptr, nullptr, nullptr, 2},
        {nullptr, nullptr, nullptr, nullptr, 3},  /* antialiasing: runtime */
        {nullptr, nullptr, nullptr, kOvlOnOff, 2},
        {nullptr, nullptr, nullptr, kOvlSmooth, 3},
        {nullptr, nullptr, nullptr, kOvlTexture, 4},"""
_L6_HELPERS = """std::atomic<int> g_ovl_sess_aa{-1}, g_ovl_sess_dither{-1};
/* ---- Spyro Trilogy: look rows on the player settings (settings.toml) ---- */
std::atomic<int> g_spyro_sess_ires{-1};
const int kSpyroIresScale[] = {1, 2, 3, 4, 5, 6, 8};
std::string spyro_setting(const PSXRecompV4::UserSettings& us, const char* key) {
    const auto it = us.extra_player_settings.find(key);
    return it == us.extra_player_settings.end() ? std::string() : it->second;
}
bool spyro_saved_row(int setting) {
    return setting == PSX_MENU_SESSION_PGXP || setting == PSX_MENU_SESSION_CRT_FILTER ||
           setting == PSX_MENU_SESSION_SCANLINES || setting == PSX_MENU_SESSION_SMOOTHING ||
           setting == PSX_MENU_SESSION_TEXTURE_FILTERING;
}
/* 1 = handled (value in *out), 0 = not one of ours. */
int spyro_look_get(int setting, int* out) {
    if (setting == PSX_MENU_SESSION_INTERNAL_RESOLUTION) {
        const int scale = g_video_scale > 0 ? g_video_scale : 1;
        int best = 0;
        for (int i = 1; i < 7; ++i)
            if (std::abs(kSpyroIresScale[i] - scale) < std::abs(kSpyroIresScale[best] - scale)) best = i;
        *out = best;
        return 1;
    }
    if (!spyro_saved_row(setting)) return 0;
    PSXRecompV4::UserSettings us;
    try {
        if (!g_overlay_settings_path.empty()) us = PSXRecompV4::load_user_settings(g_overlay_settings_path);
    } catch (...) {
    }
    switch (setting) {
    case PSX_MENU_SESSION_PGXP: *out = spyro_setting(us, "video.geometry_correction") == "true"; break;
    case PSX_MENU_SESSION_CRT_FILTER: {
        const std::string v = spyro_setting(us, "video.crt_filter");
        *out = !v.empty() && v != "raw";
        break;
    }
    case PSX_MENU_SESSION_SCANLINES: *out = spyro_setting(us, "video.scanlines") == "true"; break;
    case PSX_MENU_SESSION_SMOOTHING: {
        const std::string v = spyro_setting(us, "video.antialiasing");
        *out = v == "true" ? 1 : v == "false" ? 2 : 0;
        break;
    }
    default: {
        const std::string v = spyro_setting(us, "video.texture_filtering");
        *out = v == "nearest" ? 1 : (v == "bilinear" || v == "stable") ? 2 : v == "xbr" ? 3 : 0;
    }
    }
    return 1;
}
/* -1 = not ours; else the session_set result. */
int spyro_look_set(int setting, int value) {
    if (setting == PSX_MENU_SESSION_INTERNAL_RESOLUTION) {
        if (value < 0 || value > 6) return 0;
        g_spyro_sess_ires = value;              /* applied live on the main thread */
        return 1;
    }
    if (!spyro_saved_row(setting)) return -1;
    if (psx_netplay_active() || g_overlay_settings_path.empty()) return 0;
    try {
        PSXRecompV4::UserSettings us = PSXRecompV4::load_user_settings(g_overlay_settings_path);
        auto& x = us.extra_player_settings;
        switch (setting) {
        case PSX_MENU_SESSION_PGXP:
            x["video.geometry_correction"] = value ? "true" : "false";
            x["video.perspective_texturing"] = value ? "true" : "false";
            break;
        case PSX_MENU_SESSION_CRT_FILTER: x["video.crt_filter"] = value ? "crt" : "raw"; break;
        case PSX_MENU_SESSION_SCANLINES: x["video.scanlines"] = value ? "true" : "false"; break;
        case PSX_MENU_SESSION_SMOOTHING:
            if (value == 0) x.erase("video.antialiasing");
            else x["video.antialiasing"] = value == 1 ? "true" : "false";
            break;
        default: {
            static const char* const kTex[] = {nullptr, "nearest", "bilinear", "xbr"};
            if (value < 0 || value > 3) return 0;
            if (!kTex[value]) x.erase("video.texture_filtering");
            else x["video.texture_filtering"] = kTex[value];
        }
        }
        if (!PSXRecompV4::save_user_settings(g_overlay_settings_path, us)) return 0;
    } catch (...) {
        return 0;
    }
    return PSX_MENU_SESSION_AT_RESTART;
}
"""
_L6_GET_OLD = """int ovl_look_get(int setting, int* out) {
    if (!g_ovl_look_posted_init || !ovl_look_catalog_available(setting)) return 0;
    const int posted = g_ovl_look_posted[setting].load();
    if (posted >= 0) { *out = posted; return 1; }
"""
_L6_GET_NEW = _L6_GET_OLD + """    if (spyro_look_get(setting, out)) {
        if (setting != PSX_MENU_SESSION_INTERNAL_RESOLUTION)
            g_ovl_look_posted[setting] = *out;   /* read settings.toml once per session */
        return 1;
    }
"""
_L6_SET_OLD = """int ovl_look_set(int setting, int value) {
    if (!g_ovl_look_posted_init || !ovl_look_catalog_available(setting)) return 0;
    int rc = 1;
"""
_L6_SET_NEW = """int ovl_look_set(int setting, int value) {
    if (!g_ovl_look_posted_init || !ovl_look_catalog_available(setting)) return 0;
    {
        const int spyro_rc = spyro_look_set(setting, value);
        if (spyro_rc >= 0) {
            if (spyro_rc && setting != PSX_MENU_SESSION_INTERNAL_RESOLUTION)
                g_ovl_look_posted[setting] = value;
            return spyro_rc;
        }
    }
    int rc = 1;
"""
_L6_SVC_OLD = """void ovl_look_service(void) {
    const int aa = g_ovl_sess_aa.exchange(-1);"""
_L6_SVC_NEW = """void ovl_look_service(void) {
    {
        const int ires = g_spyro_sess_ires.exchange(-1);
        if (ires >= 0 && ires < 7) {
            PsxHostVideoSettings next;
            psx_video_current(&next);
            next.internal_resolution = PSX_IR_SCALE(kSpyroIresScale[ires]);
            (void)psx_video_apply_live(&next);   /* applies now and saves settings.toml */
        }
    }
    const int aa = g_ovl_sess_aa.exchange(-1);"""
PATCHES += [
    (_MAIN, _L6_ROWS_OLD, _L6_ROWS_NEW),
    (_MAIN, "std::atomic<int> g_ovl_sess_aa{-1}, g_ovl_sess_dither{-1};\n", _L6_HELPERS),
    (_MAIN, _L6_GET_OLD, _L6_GET_NEW),
    (_MAIN, _L6_SET_OLD, _L6_SET_NEW),
    (_MAIN, _L6_SVC_OLD, _L6_SVC_NEW),
]

def apply(root: Path) -> None:
    """Apply all patches under the framework root (idempotent).

    A patch counts as applied when its new text is present, or when a later
    patch rewrote part of it (its old text lies inside this patch's new text)
    and that later patch is applied.
    """
    marker = root / f".{PATCH_LEVEL}"
    if marker.exists():
        return
    by_file: dict[str, list[tuple[str, str]]] = {}
    for rel, old, new in PATCHES:
        by_file.setdefault(rel, []).append((old, new))
    for rel, edits in by_file.items():
        path = root / rel
        text = path.read_text(encoding="utf-8")

        def applied(i: int) -> bool:
            if edits[i][1] in text:
                return True
            return any(edits[j][0] in edits[i][1] and applied(j) for j in range(i + 1, len(edits)))

        for i, (old, new) in enumerate(edits):
            if applied(i):
                continue
            if text.count(old) != 1:
                raise RuntimeError(f"Framework patch does not fit {rel}: {old[:60]!r}")
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8", newline="\n")
    marker.write_text(PATCH_LEVEL)
