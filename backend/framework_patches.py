"""Small, verified edits to the downloaded framework.

Each patch is (relative path, exact old text, new text). A patch whose new
text is already present is skipped; a patch whose old text is missing stops
the setup with a clear error instead of building something half-patched.
"""
from __future__ import annotations

from pathlib import Path

PATCH_LEVEL = "spyro-patches-3"

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


def apply(root: Path) -> None:
    """Apply all patches under the framework root (idempotent)."""
    marker = root / f".{PATCH_LEVEL}"
    if marker.exists():
        return
    by_file: dict[str, list[tuple[str, str]]] = {}
    for rel, old, new in PATCHES:
        by_file.setdefault(rel, []).append((old, new))
    for rel, edits in by_file.items():
        path = root / rel
        text = path.read_text(encoding="utf-8")
        for old, new in edits:
            if new in text:
                continue
            if text.count(old) != 1:
                raise RuntimeError(f"Framework patch does not fit {rel}: {old[:60]!r}")
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8", newline="\n")
    marker.write_text(PATCH_LEVEL)
