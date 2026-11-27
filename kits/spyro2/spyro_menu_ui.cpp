/* spyro_menu_ui.cpp -- the in-game menu, drawn in Spyro Trilogy's style.
 *
 * recomp-ui keeps the menu's model (sections, rows, values, navigation,
 * saving); this file only draws it, with Dear ImGui, to match the Spyro
 * Trilogy app: twilight panel, the game's gem, Fredoka headings, Atkinson
 * Hyperlegible text, toggles and sliders, controller or keyboard hints.
 *
 * Needs the Spyro framework patch (level 4) that adds
 * recomp_runtime_ui_custom_render / _fonts_hook / _last_input_pad.
 * SPYRO_GAME (1, 2 or 3) is set by the game's CMakeLists.txt.
 */
#if defined(RECOMP_LAUNCHER) && defined(__has_include)
#if __has_include("recomp_runtime_ui_internal.h") && __has_include("imgui.h") && \
    __has_include("imgui_impl_opengl3.h")
#define SPYRO_HAS_UI 1
#endif
#endif

#if defined(SPYRO_HAS_UI)
#include "recomp_runtime_ui_internal.h"
#include "imgui.h"
#include "imgui_impl_opengl3.h"

#include <algorithm>
#include <cfloat>
#include <initializer_list>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>

#ifndef SPYRO_GAME
#define SPYRO_GAME 1
#endif

extern "C" {
extern void (*recomp_runtime_ui_custom_render)(RecompRuntimeUi *);
extern void (*recomp_runtime_ui_fonts_hook)(int, int);
extern int recomp_runtime_ui_last_input_pad;
extern const char *(*recomp_runtime_ui_translate)(const char *);
}

namespace {

/* ------------------------------------------------------------------ look */
ImU32 rgb(unsigned hex, float a = 1.0f) {
    return IM_COL32((hex >> 16) & 255, (hex >> 8) & 255, hex & 255,
                    (int)std::lround(std::clamp(a, 0.0f, 1.0f) * 255.0f));
}
ImU32 white(float a) { return IM_COL32(255, 255, 255, (int)std::lround(a * 255.0f)); }

constexpr unsigned kDusk = 0x24174A, kText = 0xF4EFFF, kMist = 0xB9AEE0,
                   kInk = 0x1A0F33, kEmber = 0xFF8A4C, kDanger = 0xFF6B7A,
                   kEmerald = 0x33C9A0, kPadA = 0x6BE38A, kPadB = 0xFF7F8F,
                   kCross = 0x8FB2FF, kGold = 0xF5B82E;

struct World { const char *title; unsigned g1, g2, g3; };
#if SPYRO_GAME == 2
constexpr World kWorld = {"Spyro 2: Gateway to Glimmer", 0xB8FFE8, 0x33C9A0, 0x137A68};
#elif SPYRO_GAME == 3
constexpr World kWorld = {"Spyro: Year of the Dragon", 0xEADCFF, 0xB086FF, 0x5D38B0};
#else
constexpr World kWorld = {"Spyro the Dragon", 0xFFE3A3, 0xF5B82E, 0xC26A14};
#endif

const char *TR(const char *s) {
    return (s && recomp_runtime_ui_translate) ? recomp_runtime_ui_translate(s) : (s ? s : "");
}

/* ----------------------------------------------------------------- fonts */
std::string g_font_dir;  // ".../assets/spyro"
struct Fonts {
    ImFont *body = nullptr, *bold = nullptr, *small = nullptr;
    ImFont *title = nullptr, *head = nullptr, *key = nullptr;
    float scale = 0.0f;
} F;

bool file_exists(const std::string &p) {
    if (FILE *f = std::fopen(p.c_str(), "rb")) { std::fclose(f); return true; }
    return false;
}

void fonts_hook(int w, int h) {
    const float s = std::clamp(std::min(w, h) / 720.0f, 1.0f, 3.0f);
    if (F.body && std::fabs(s - F.scale) < 0.08f) return;
    ImGuiIO &io = ImGui::GetIO();
    if (F.body && io.BackendRendererUserData) ImGui_ImplOpenGL3_DestroyFontsTexture();
    io.Fonts->Clear();
    /* Latin-1, punctuation (German quotes, ‹ ›), arrows, geometric shapes */
    static const ImWchar ranges[] = {0x0020, 0x00FF, 0x2010, 0x203A, 0x2190, 0x21FF,
                                     0x25A0, 0x25FF, 0};
    auto add = [&](const char *file, float px) -> ImFont * {
        const std::string p = g_font_dir + "/" + file;
        ImFontConfig cfg;
        cfg.OversampleH = 2;
        cfg.OversampleV = 1;
        ImFont *f = file_exists(p)
            ? io.Fonts->AddFontFromFileTTF(p.c_str(), std::round(px * s), &cfg, ranges)
            : nullptr;
        if (!f) {
            ImFontConfig d;
            d.SizePixels = std::round(px * s);
            f = io.Fonts->AddFontDefault(&d);
        }
        return f;
    };
    F.body = add("SpyroMenu-Regular.ttf", 16.0f);   // first font = ImGui default
    F.bold = add("SpyroMenu-Bold.ttf", 16.0f);
    F.small = add("SpyroMenu-Regular.ttf", 13.5f);
    F.title = add("SpyroMenu-Display.ttf", 24.0f);
    F.head = add("SpyroMenu-Display.ttf", 16.5f);
    F.key = add("SpyroMenu-Display.ttf", 13.0f);
    F.scale = s;
}

/* -------------------------------------------------------------- drawing */
ImVec2 text_size(ImFont *f, const char *t, float wrap = 0.0f) {
    return f->CalcTextSizeA(f->FontSize, FLT_MAX, wrap, t);
}
void text(ImDrawList *dl, ImFont *f, ImVec2 p, ImU32 c, const char *t, float wrap = 0.0f) {
    dl->AddText(f, f->FontSize, p, c, t, nullptr, wrap);
}

/* The app's gem (index.html), scaled into a w x h box. */
void gem(ImDrawList *dl, ImVec2 o, float w, float h, const World &wd, float a = 1.0f) {
    auto P = [&](float x, float y) { return ImVec2(o.x + (x - 5.0f) / 190.0f * w, o.y + (y - 40.0f) / 132.0f * h); };
    auto poly = [&](std::initializer_list<ImVec2> pts, ImU32 c) {
        ImVec2 v[4]; int n = 0;
        for (const ImVec2 &p : pts) v[n++] = p;
        dl->AddConvexPolyFilled(v, n, c);
    };
    const unsigned g3dark = ((((wd.g3 >> 16) & 255) * 7 / 10) << 16) |
                            ((((wd.g3 >> 8) & 255) * 7 / 10) << 8) | ((wd.g3 & 255) * 7 / 10);
    poly({P(40, 40), P(80, 40), P(60, 75), P(5, 75)}, rgb(wd.g2, a));
    poly({P(80, 40), P(120, 40), P(140, 75), P(60, 75)}, rgb(wd.g1, a));
    poly({P(120, 40), P(160, 40), P(195, 75), P(140, 75)}, rgb(wd.g2, a));
    poly({P(5, 75), P(60, 75), P(100, 172)}, rgb(wd.g3, a));
    poly({P(60, 75), P(140, 75), P(100, 172)}, rgb(wd.g2, a));
    poly({P(140, 75), P(195, 75), P(100, 172)}, rgb(g3dark, a));
    poly({P(88, 46), P(104, 46), P(96, 60)}, white(0.75f * a));
}

void chevron(ImDrawList *dl, ImVec2 c, float sz, bool right, ImU32 col, float th) {
    const float d = right ? 1.0f : -1.0f;
    ImVec2 pts[3] = {ImVec2(c.x - d * sz * 0.35f, c.y - sz * 0.6f), ImVec2(c.x + d * sz * 0.35f, c.y),
                     ImVec2(c.x - d * sz * 0.35f, c.y + sz * 0.6f)};
    dl->AddPolyline(pts, 3, col, 0, th);
}

void toggle(ImDrawList *dl, ImVec2 p, float s, bool on, float a) {
    const float w = 50 * s, h = 28 * s, r = h * 0.5f;
    dl->AddRectFilled(p, ImVec2(p.x + w, p.y + h), on ? rgb(kWorld.g2, a) : white(0.15f * a), r);
    const float kx = on ? p.x + w - r : p.x + r;
    dl->AddCircleFilled(ImVec2(kx, p.y + r), 11 * s, white(a), 24);
}

/* A keyboard key chip; returns its width. */
float key_chip(ImDrawList *dl, ImVec2 p, float s, const char *label, float h) {
    const ImVec2 ts = text_size(F.key, label);
    const float w = std::max(h, ts.x + 14 * s);
    dl->AddRectFilled(p, ImVec2(p.x + w, p.y + h), white(0.10f), 6 * s);
    text(dl, F.key, ImVec2(p.x + (w - ts.x) * 0.5f, p.y + (h - ts.y) * 0.5f), rgb(kText), label);
    return w;
}

/* An arrow key chip (fonts may lack arrow glyphs, so it is drawn). */
float arrow_chip(ImDrawList *dl, ImVec2 p, float s, int dir, float h) {
    dl->AddRectFilled(p, ImVec2(p.x + h, p.y + h), white(0.10f), 6 * s);
    const ImVec2 c(p.x + h * 0.5f, p.y + h * 0.5f);
    const float k = h * 0.22f;
    ImVec2 a, b, d;
    switch (dir) {
    case 0: a = {c.x, c.y - k}; b = {c.x + k, c.y + k * 0.7f}; d = {c.x - k, c.y + k * 0.7f}; break;  // up
    case 1: a = {c.x, c.y + k}; b = {c.x - k, c.y - k * 0.7f}; d = {c.x + k, c.y - k * 0.7f}; break;  // down
    case 2: a = {c.x - k, c.y}; b = {c.x + k * 0.7f, c.y - k}; d = {c.x + k * 0.7f, c.y + k}; break;  // left
    default: a = {c.x + k, c.y}; b = {c.x - k * 0.7f, c.y + k}; d = {c.x - k * 0.7f, c.y - k}; break; // right
    }
    dl->AddTriangleFilled(a, b, d, rgb(kText));
    return h;
}

/* Round controller button: a letter (A/B) or a PlayStation symbol. */
enum Pad { PAD_A, PAD_B, PAD_CROSS, PAD_CIRCLE };
float pad_chip(ImDrawList *dl, ImVec2 p, float s, Pad b, float h) {
    const ImVec2 c(p.x + h * 0.5f, p.y + h * 0.5f);
    const float r = h * 0.5f;
    dl->AddCircleFilled(c, r, white(0.10f), 24);
    if (b == PAD_A || b == PAD_B) {
        const char *t = b == PAD_A ? "A" : "B";
        const ImVec2 ts = text_size(F.key, t);
        text(dl, F.key, ImVec2(c.x - ts.x * 0.5f, c.y - ts.y * 0.5f), rgb(b == PAD_A ? kPadA : kPadB), t);
    } else if (b == PAD_CROSS) {
        const float k = r * 0.42f;
        dl->AddLine(ImVec2(c.x - k, c.y - k), ImVec2(c.x + k, c.y + k), rgb(kCross), 2.0f * s);
        dl->AddLine(ImVec2(c.x - k, c.y + k), ImVec2(c.x + k, c.y - k), rgb(kCross), 2.0f * s);
    } else {
        dl->AddCircle(c, r * 0.45f, rgb(kPadB), 20, 2.0f * s);
    }
    return h;
}

/* D-pad with the vertical or horizontal arms lit. */
float dpad(ImDrawList *dl, ImVec2 p, float s, bool vertical, float h) {
    const float t = h / 3.0f;
    const ImU32 dim = white(0.18f), lit = rgb(kGold);
    dl->AddRectFilled(ImVec2(p.x + t, p.y), ImVec2(p.x + 2 * t, p.y + h), vertical ? lit : dim, 2 * s);
    dl->AddRectFilled(ImVec2(p.x, p.y + t), ImVec2(p.x + h, p.y + 2 * t), vertical ? dim : lit, 2 * s);
    dl->AddRectFilled(ImVec2(p.x + t, p.y + t), ImVec2(p.x + 2 * t, p.y + 2 * t), white(0.25f));
    return h;
}

float pill(ImDrawList *dl, ImVec2 p, float s, const char *label, unsigned color, bool right_aligned) {
    const ImVec2 ts = text_size(F.key, label);
    const float h = ts.y + 10 * s, w = ts.x + 22 * s;
    if (right_aligned) p.x -= w;
    dl->AddRectFilled(p, ImVec2(p.x + w, p.y + h), rgb(color, 0.18f), h * 0.5f);
    dl->AddRect(p, ImVec2(p.x + w, p.y + h), rgb(color, 0.55f), h * 0.5f, 0, 1.0f);
    text(dl, F.key, ImVec2(p.x + 11 * s, p.y + 5 * s), rgb(color), label);
    return w;
}

/* ---------------------------------------------------------------- model */
bool is_danger(const RecompRuntimeUiItem *it) {
    if (!it || !it->key) return false;
    return std::strstr(it->key, "quit") || std::strstr(it->key, "reset") || std::strstr(it->key, "restart");
}

bool paused(RecompRuntimeUi *ui) {
    for (size_t i = 0; i < ui->config.item_count; ++i) {
        const RecompRuntimeUiItem *it = &ui->config.items[i];
        if (it->key && std::strcmp(it->key, RECOMP_RUNTIME_UI_KEY_PAUSE_IN_MENU) == 0) {
            int v = 0;
            return recomp_runtime_ui_current_value(ui, it, &v) && v;
        }
    }
    return false;
}

/* Game first (resume / restart / quit), then the picture, sound and input. */
void order_sections(RecompRuntimeUi *ui) {
    static bool done = false;
    if (done || ui->in_section) return;
    done = true;
    static const char *const kOrder[] = {"System", "Display", "Graphics", "Audio", "Input", "Disc"};
    const char **out = ui->sections;
    size_t n = 0;
    const size_t count = ui->section_count;
    const char *tmp[32];
    if (count > 32) return;
    bool used[32] = {};
    for (const char *want : kOrder)
        for (size_t i = 0; i < count; ++i)
            if (!used[i] && std::strcmp(ui->sections[i], want) == 0) { tmp[n++] = ui->sections[i]; used[i] = true; }
    for (size_t i = 0; i < count; ++i) if (!used[i]) tmp[n++] = ui->sections[i];
    for (size_t i = 0; i < count; ++i) out[i] = tmp[i];
    ui->section_index = 0;
}

struct Value {
    enum Kind { TEXT, TOGGLE, SLIDER, STEPPER, ACTION } kind = TEXT;
    std::string text;
    bool on = false;
    float frac = 0.0f;
};

Value value_of(RecompRuntimeUi *ui, const RecompRuntimeUiItem *it) {
    Value v;
    if (it->type == RECOMP_RUNTIME_UI_ACTION) { v.kind = Value::ACTION; return v; }
    if (it->type == RECOMP_RUNTIME_UI_TEXT) {
        char buf[128];
        recomp_runtime_ui_current_text(ui, it, buf, sizeof buf);
        v.text = buf[0] ? buf : TR("(not set)");
        return v;
    }
    int x = 0;
    if (!recomp_runtime_ui_current_value(ui, it, &x)) { v.text = TR("Unavailable"); return v; }
    if (it->type == RECOMP_RUNTIME_UI_BOOL) { v.kind = Value::TOGGLE; v.on = x != 0; return v; }
    if (it->type == RECOMP_RUNTIME_UI_CHOICE && it->choices) {
        size_t idx = it->choice_count;
        if (it->choice_values) {
            for (size_t i = 0; i < it->choice_count; ++i) if (it->choice_values[i] == x) { idx = i; break; }
        } else if (x >= it->minimum && (size_t)(x - it->minimum) < it->choice_count) {
            idx = (size_t)(x - it->minimum);
        }
        v.kind = Value::STEPPER;
        v.text = idx < it->choice_count ? TR(it->choices[idx]) : TR("Unavailable");
        return v;
    }
    char buf[32];
    if (it->key && std::strcmp(it->key, RECOMP_RUNTIME_UI_KEY_GYRO_SENSITIVITY) == 0)
        std::snprintf(buf, sizeof buf, "%.2fx", x / 100.0f);
    else
        std::snprintf(buf, sizeof buf, "%d", x);
    v.text = buf;
    const int range = it->maximum - it->minimum;
    if (range >= 10 && range <= 1000) {
        v.kind = Value::SLIDER;
        v.frac = std::clamp((float)(x - it->minimum) / (float)range, 0.0f, 1.0f);
    } else {
        v.kind = Value::STEPPER;
    }
    return v;
}

/* Width the value needs on the right of a row. */
float value_width(const Value &v, float s, bool selected) {
    switch (v.kind) {
    case Value::TOGGLE: return 50 * s;
    case Value::SLIDER: return 150 * s + 12 * s + std::max(text_size(F.bold, v.text.c_str()).x, 34 * s);
    case Value::STEPPER: return text_size(F.bold, v.text.c_str()).x + (selected ? 44 * s : 0);
    case Value::ACTION: return 14 * s;
    default: return text_size(F.body, v.text.c_str()).x;
    }
}

void draw_value(ImDrawList *dl, const Value &v, ImVec2 right_mid, float s, bool selected,
                bool danger, float a) {
    const float w = value_width(v, s, selected);
    float x = right_mid.x - w;
    const float y = right_mid.y;
    switch (v.kind) {
    case Value::TOGGLE:
        toggle(dl, ImVec2(x, y - 14 * s), s, v.on, a);
        break;
    case Value::SLIDER: {
        const float bw = 150 * s, bh = 6 * s;
        const ImVec2 b0(x, y - bh * 0.5f), b1(x + bw, y + bh * 0.5f);
        dl->AddRectFilled(b0, b1, white(0.15f * a), bh);
        dl->AddRectFilled(b0, ImVec2(x + bw * v.frac, b1.y), rgb(kWorld.g2, a), bh);
        dl->AddCircleFilled(ImVec2(x + bw * v.frac, y), 8 * s, white(a), 20);
        const ImVec2 ts = text_size(F.bold, v.text.c_str());
        text(dl, F.bold, ImVec2(right_mid.x - ts.x, y - ts.y * 0.5f), rgb(kText, a), v.text.c_str());
        break;
    }
    case Value::STEPPER: {
        const ImVec2 ts = text_size(F.bold, v.text.c_str());
        if (selected) {
            chevron(dl, ImVec2(x + 6 * s, y), 9 * s, false, rgb(kWorld.g2, a), 2.0f * s);
            chevron(dl, ImVec2(right_mid.x - 6 * s, y), 9 * s, true, rgb(kWorld.g2, a), 2.0f * s);
            x += 22 * s;
        }
        text(dl, F.bold, ImVec2(x, y - ts.y * 0.5f), rgb(selected ? kText : kMist, a), v.text.c_str());
        break;
    }
    case Value::ACTION:
        chevron(dl, ImVec2(right_mid.x - 6 * s, y), 10 * s, true,
                danger ? rgb(kDanger, a) : rgb(selected ? kWorld.g2 : kMist, a), 2.2f * s);
        break;
    default: {
        const ImVec2 ts = text_size(F.body, v.text.c_str());
        text(dl, F.body, ImVec2(x, y - ts.y * 0.5f), rgb(kMist, a), v.text.c_str());
    }
    }
}

/* -------------------------------------------------------------- the menu */
std::string page_title(RecompRuntimeUi *ui) {
    char raw[256];
    recomp_runtime_ui_page_title(ui, raw, sizeof raw);
    std::string out, part;
    for (const char *c = raw;; ++c) {
        if (*c == '/' || !*c) {
            if (!out.empty()) out += "  ›  ";
            out += TR(part.c_str());
            part.clear();
            if (!*c) break;
        } else {
            part += *c;
        }
    }
    return out;
}

void draw_hints(ImDrawList *dl, ImVec2 p, float s, bool in_section) {
    const bool pad = recomp_runtime_ui_last_input_pad != 0;
    const float h = 24 * s, gap = 5 * s, group = 22 * s;
    auto label = [&](const char *t) {
        const ImVec2 ts = text_size(F.small, TR(t));
        p.x += 8 * s;
        text(dl, F.small, ImVec2(p.x, p.y + (h - ts.y) * 0.5f), rgb(kMist), TR(t));
        p.x += ts.x + group;
    };
    // Accept
    if (pad) { p.x += pad_chip(dl, p, s, PAD_A, h) + gap; p.x += pad_chip(dl, p, s, PAD_CROSS, h); }
    else p.x += key_chip(dl, p, s, "Enter", h);
    label(in_section ? "Select" : "Open");
    if (in_section) {  // Change
        if (pad) p.x += dpad(dl, p, s, false, h);
        else { p.x += arrow_chip(dl, p, s, 2, h) + gap; p.x += arrow_chip(dl, p, s, 3, h); }
        label("Change");
    }
    // Navigate
    if (pad) p.x += dpad(dl, p, s, true, h);
    else { p.x += arrow_chip(dl, p, s, 0, h) + gap; p.x += arrow_chip(dl, p, s, 1, h); }
    label("Navigate");
    // Back / close
    if (pad) { p.x += pad_chip(dl, p, s, PAD_B, h) + gap; p.x += pad_chip(dl, p, s, PAD_CIRCLE, h); }
    else p.x += key_chip(dl, p, s, "Esc", h);
    label(in_section ? "Back" : "Resume game");
}

/* Selection changes scroll the row into view once (it must not fight scrolling). */
struct Reveal { size_t section = (size_t)-1, row = (size_t)-1; int in = -1; char page[192] = {}; } g_reveal;

void draw_rows(RecompRuntimeUi *ui, float s, float width) {
    ImDrawList *dl = ImGui::GetWindowDrawList();
    const bool changed = g_reveal.section != ui->section_index || g_reveal.row != ui->row_index ||
                         g_reveal.in != ui->in_section || std::strcmp(g_reveal.page, ui->page) != 0;
    g_reveal.section = ui->section_index; g_reveal.row = ui->row_index; g_reveal.in = ui->in_section;
    std::snprintf(g_reveal.page, sizeof g_reveal.page, "%s", ui->page);

    const float padx = 16 * s, pady = 13 * s;
    /* Rows of the highlighted section, also while the player is still choosing
     * a section (then nothing in it is selected). */
    size_t count;
    if (ui->in_section) count = recomp_runtime_ui_page_entry_count(ui);
    else count = recomp_runtime_ui_section_item_count(ui, ui->section_index);
    for (size_t i = 0; i < count; ++i) {
        char folder[96] = "";
        const RecompRuntimeUiItem *it = ui->in_section
            ? recomp_runtime_ui_page_entry(ui, i, folder, sizeof folder)
            : recomp_runtime_ui_section_item(ui, ui->section_index, i);
        if (!it && !folder[0]) continue;
        const bool selected = ui->in_section && i == ui->row_index;
        const bool enabled = !it || recomp_runtime_ui_item_enabled(ui, it);
        const float a = enabled ? 1.0f : 0.42f;
        const bool danger = is_danger(it);
        const char *label = it ? TR(it->label) : TR(folder);
        /* "Press again to ..." replaces the row's description while it is up */
        const bool confirming = selected && it && it->type == RECOMP_RUNTIME_UI_ACTION && ui->status_frames &&
                                (ui->confirm_item == it || std::strncmp(ui->status, "Press again", 11) == 0);
        const char *desc = confirming ? TR(ui->status)
                         : it && it->description && it->description[0] ? TR(it->description) : nullptr;

        Value v;
        if (it) v = value_of(ui, it); else v.kind = Value::ACTION;
        const float vw = value_width(v, s, selected);
        const float label_w = std::max(10.0f, width - 2 * padx - vw - 16 * s);
        const ImVec2 ls = text_size(F.bold, label, label_w);
        const float desc_h = desc ? text_size(F.small, desc, width - 2 * padx).y + 4 * s : 0.0f;
        const float row_h = pady * 2 + std::max(ls.y, 28 * s) + desc_h;

        const ImVec2 p0 = ImGui::GetCursorScreenPos();
        const ImVec2 p1(p0.x + width, p0.y + row_h);
        ImGui::Dummy(ImVec2(width, row_h));
        if (selected && changed) {
            const float top = ImGui::GetWindowPos().y, bottom = top + ImGui::GetWindowHeight();
            if (p0.y < top) ImGui::SetScrollHereY(0.0f);
            else if (p1.y > bottom) ImGui::SetScrollHereY(1.0f);
        }
        if (i > 0 && !selected && !(ui->in_section && i == ui->row_index + 1))
            dl->AddLine(ImVec2(p0.x + padx, p0.y), ImVec2(p1.x - padx, p0.y), white(0.07f));
        if (selected) {
            dl->AddRectFilled(p0, p1, white(0.08f), 12 * s);
            dl->AddRectFilled(ImVec2(p0.x, p0.y + 10 * s), ImVec2(p0.x + 4 * s, p1.y - 10 * s),
                              rgb(danger ? kDanger : kWorld.g2), 2 * s);
        }
        const float line_mid = p0.y + pady + std::max(ls.y, 28 * s) * 0.5f;
        text(dl, F.bold, ImVec2(p0.x + padx, line_mid - ls.y * 0.5f),
             rgb(danger && selected ? 0xFFB3BB : kText, a), label, label_w);
        if (desc)
            text(dl, F.small, ImVec2(p0.x + padx, line_mid + std::max(ls.y, 28 * s) * 0.5f + 4 * s),
                 rgb(confirming ? kEmber : kMist, a), desc, width - 2 * padx);
        draw_value(dl, v, ImVec2(p1.x - padx, line_mid), s, selected, danger || confirming, a);
    }
    ImGui::Dummy(ImVec2(width, 8 * s));
    /* soft edges where the list scrolls under the page title / the footer */
    const ImVec2 wp = ImGui::GetWindowPos(), ws = ImGui::GetWindowSize();
    const float fade = 22 * s;
    const ImU32 solid = rgb(kDusk, std::clamp(ui->opacity, 0.0f, 1.0f)), clear = rgb(kDusk, 0.0f);
    if (ImGui::GetScrollY() > 0.5f)
        dl->AddRectFilledMultiColor(wp, ImVec2(wp.x + ws.x, wp.y + fade), solid, solid, clear, clear);
    if (ImGui::GetScrollY() < ImGui::GetScrollMaxY() - 0.5f)
        dl->AddRectFilledMultiColor(ImVec2(wp.x, wp.y + ws.y - fade), ImVec2(wp.x + ws.x, wp.y + ws.y),
                                    clear, clear, solid, solid);
}

void draw_toast(RecompRuntimeUi *ui) {
    ImDrawList *dl = ImGui::GetForegroundDrawList();
    const float s = F.scale > 0 ? F.scale : 1.0f;
    const ImVec2 display = ImGui::GetIO().DisplaySize;
    const char *title = ui->toast_title[0] ? TR(ui->toast_title) : nullptr;
    const char *body = ui->toast_body[0] ? TR(ui->toast_body) : nullptr;
    const float maxw = std::min(display.x - 40 * s, 520 * s);
    const ImVec2 ts = title ? text_size(F.bold, title, maxw) : ImVec2(0, 0);
    const ImVec2 bs = body ? text_size(F.small, body, maxw) : ImVec2(0, 0);
    const float w = std::max(ts.x, bs.x) + 36 * s;
    const float h = ts.y + bs.y + (title && body ? 6 * s : 0) + 24 * s;
    const ImVec2 p0(display.x * 0.5f - w * 0.5f, 20 * s), p1(p0.x + w, p0.y + h);
    dl->AddRectFilled(p0, p1, rgb(kDusk, 0.96f * ui->opacity), 14 * s);
    dl->AddRect(p0, p1, rgb(kWorld.g2, 0.7f), 14 * s, 0, 1.5f * s);
    float y = p0.y + 12 * s;
    if (title) { text(dl, F.bold, ImVec2(p0.x + 18 * s, y), rgb(kWorld.g1), title, maxw); y += ts.y + 6 * s; }
    if (body) text(dl, F.small, ImVec2(p0.x + 18 * s, y), rgb(kText), body, maxw);
}

void render(RecompRuntimeUi *ui) {
    if (!F.body) return;  // fonts not loaded (no fonts hook): nothing sensible to draw
    if (!ui->open) {
        if (recomp_runtime_ui_toast_visible(ui)) draw_toast(ui);
        return;
    }
    order_sections(ui);
    ImGuiIO &io = ImGui::GetIO();
    const ImVec2 display = io.DisplaySize;
    if (display.x <= 0 || display.y <= 0) return;
    const float s = F.scale;

    /* the game behind, darkened and tinted towards the app's twilight */
    ImGui::GetBackgroundDrawList()->AddRectFilled(ImVec2(0, 0), display,
        IM_COL32(8, 4, 20, (int)std::lround(255.0f * std::clamp(ui->dim, 0.0f, 1.0f))));

    const float margin = 24 * s;
    const float W = std::min(display.x - 2 * margin, 960 * s);
    const float H = std::min(display.y - 2 * margin, 640 * s);
    const ImVec2 p0((display.x - W) * 0.5f, (display.y - H) * 0.5f), p1(p0.x + W, p0.y + H);

    ImGui::SetNextWindowPos(p0);
    ImGui::SetNextWindowSize(ImVec2(W, H));
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(0, 0));
    ImGui::PushStyleVar(ImGuiStyleVar_WindowBorderSize, 0.0f);
    ImGui::PushStyleVar(ImGuiStyleVar_ItemSpacing, ImVec2(0, 0));
    ImGui::PushStyleVar(ImGuiStyleVar_ScrollbarSize, 6 * s);
    ImGui::PushStyleVar(ImGuiStyleVar_ScrollbarRounding, 3 * s);
    ImGui::PushStyleColor(ImGuiCol_ScrollbarBg, IM_COL32(0, 0, 0, 0));
    ImGui::PushStyleColor(ImGuiCol_ScrollbarGrab, white(0.18f));
    ImGui::PushStyleColor(ImGuiCol_ScrollbarGrabHovered, white(0.25f));
    ImGui::PushStyleColor(ImGuiCol_ScrollbarGrabActive, white(0.3f));
    ImGui::PushFont(F.body);
    const ImGuiWindowFlags flags = ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_NoMove |
                                   ImGuiWindowFlags_NoSavedSettings | ImGuiWindowFlags_NoBackground |
                                   ImGuiWindowFlags_NoScrollWithMouse |
                                   (ui->editing_text ? 0 : ImGuiWindowFlags_NoNavInputs);
    if (ImGui::Begin("##spyro-menu", nullptr, flags)) {
        ImDrawList *dl = ImGui::GetWindowDrawList();
        const float R = 22 * s, pad = 28 * s;
        /* panel, with a faint glow of the game's colour behind the gem */
        dl->AddRectFilled(p0, p1, rgb(kDusk, std::clamp(ui->opacity, 0.0f, 1.0f)), R);
        dl->PushClipRect(p0, p1, true);
        for (int k = 0; k < 24; ++k)
            dl->AddCircleFilled(ImVec2(p0.x + 60 * s, p0.y + 44 * s), (260 - k * 10) * s,
                                rgb(kWorld.g2, 0.0045f), 64);
        dl->PopClipRect();
        dl->AddRect(p0, p1, white(0.08f), R, 0, 1.0f);

        /* header: gem, game title, "Game menu", paused pill */
        const float gem_w = 46 * s, gem_h = 42 * s;
        gem(dl, ImVec2(p0.x + pad, p0.y + pad), gem_w, gem_h, kWorld);
        const float tx = p0.x + pad + gem_w + 16 * s;
        const ImVec2 tsz = text_size(F.title, kWorld.title);
        const ImVec2 ssz = text_size(F.small, TR("Game menu"));
        const float ty = p0.y + pad + (gem_h - tsz.y - ssz.y) * 0.5f;
        text(dl, F.title, ImVec2(tx, ty), rgb(kText), kWorld.title);
        text(dl, F.small, ImVec2(tx, ty + tsz.y), rgb(kMist), TR("Game menu"));
        const float pill_y = p0.y + pad + gem_h * 0.5f - (text_size(F.key, "X").y + 10 * s) * 0.5f;
        float pill_x = p1.x - pad;
        if (paused(ui)) pill_x -= pill(dl, ImVec2(pill_x, pill_y), s, TR("Paused"), kWorld.g1, true) + 8 * s;
        /* "Saved" and the like; a "Press again" prompt shows on its row instead */
        if (ui->status_frames && !ui->confirm_item && std::strncmp(ui->status, "Press again", 11) != 0)
            pill(dl, ImVec2(pill_x, pill_y), s, TR(ui->status), kEmerald, true);

        /* footer */
        const float hint_h = 24 * s;
        const float foot_y = p1.y - pad - hint_h;
        dl->AddLine(ImVec2(p0.x + pad, foot_y - 18 * s), ImVec2(p1.x - pad, foot_y - 18 * s), white(0.08f));
        draw_hints(dl, ImVec2(p0.x + pad, foot_y), s, ui->in_section != 0);
        if (ui->status_frames) recomp_runtime_ui_advance_status(ui, io.DeltaTime * 60.0f);

        /* body: section list on the left, the page on the right */
        const float body_y = p0.y + pad + gem_h + 26 * s;
        const float body_h = foot_y - 18 * s - 14 * s - body_y;
        const float nav_w = 196 * s, nav_x = p0.x + pad;
        const float item_h = 42 * s, item_gap = 4 * s;
        for (size_t i = 0; i < ui->section_count; ++i) {
            const ImVec2 a(nav_x, body_y + i * (item_h + item_gap)), b(nav_x + nav_w, a.y + item_h);
            const bool sel = i == ui->section_index;
            if (sel) {
                dl->AddRectFilled(a, b, white(ui->in_section ? 0.07f : 0.12f), item_h * 0.5f);
                if (!ui->in_section)
                    dl->AddRect(a, b, rgb(kWorld.g2, 0.9f), item_h * 0.5f, 0, 2.0f * s);
            }
            const char *name = TR(ui->sections[i]);
            const ImVec2 ns = text_size(F.head, name);
            if (sel) dl->AddCircleFilled(ImVec2(a.x + 20 * s, a.y + item_h * 0.5f), 4 * s, rgb(kWorld.g2), 12);
            text(dl, F.head, ImVec2(a.x + 34 * s, a.y + (item_h - ns.y) * 0.5f),
                 rgb(sel ? kText : kMist), name);
        }

        const float page_x = nav_x + nav_w + 24 * s;
        const float page_w = p1.x - pad - page_x;
        const std::string title = page_title(ui);
        text(dl, F.head, ImVec2(page_x + 16 * s, body_y + 10 * s), rgb(kWorld.g1), title.c_str());
        const float list_y = body_y + 10 * s + text_size(F.head, "X").y + 12 * s;
        ImGui::SetCursorScreenPos(ImVec2(page_x, list_y));
        ImGui::BeginChild("##page", ImVec2(page_w, body_y + body_h - list_y), ImGuiChildFlags_None,
                          ImGuiWindowFlags_NoBackground | ImGuiWindowFlags_NoSavedSettings |
                              ImGuiWindowFlags_NoScrollWithMouse |
                              (ui->editing_text ? 0 : ImGuiWindowFlags_NoNavInputs));
        draw_rows(ui, s, page_w - (ImGui::GetScrollMaxY() > 0 ? 10 * s : 0));
        ImGui::EndChild();
    }
    ImGui::End();
    ImGui::PopFont();
    ImGui::PopStyleColor(4);
    ImGui::PopStyleVar(5);
    if (recomp_runtime_ui_toast_visible(ui)) draw_toast(ui);
}

}  // namespace

/* Called by spyro_menu.cpp when the menu attaches. */
void spyro_menu_ui_install(const char *assets_dir) {
    if (!assets_dir || !assets_dir[0]) return;  // no fonts: keep recomp-ui's own look
    g_font_dir = std::string(assets_dir) + "/spyro";
    recomp_runtime_ui_fonts_hook = fonts_hook;
    recomp_runtime_ui_custom_render = render;
}

#else
void spyro_menu_ui_install(const char *) {}
#endif
