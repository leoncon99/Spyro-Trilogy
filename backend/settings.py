"""Per-game player settings, stored in the game's own settings.toml.

The runtime reads <product>/settings.toml at start (player settings override
the title baseline in game.toml). We edit a small, friendly subset and keep
every other key untouched (tomlkit round-trip).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import tomlkit

from .catalog import Game

# id -> (section, key, kind, choices/(min,max), default, label, group, help)
# kind: choice (value stored as given), bool, int
SCHEMA: list[dict[str, Any]] = [
    {"id": "fullscreen", "section": "video", "key": "fullscreen", "kind": "choice", "default": 1,
     "choices": [[0, "Windowed"], [1, "Fullscreen (borderless)"], [2, "Exclusive fullscreen"]],
     "label": "Display mode", "group": "display",
     "help": "Borderless fullscreen switches fastest between game and desktop."},
    {"id": "vsync", "section": "video", "key": "vsync", "kind": "choice", "default": "on",
     "choices": [["on", "On"], ["adaptive", "Adaptive"], ["off", "Off (lowest latency)"]],
     "label": "VSync", "group": "display",
     "help": "Prevents tearing. \"Off\" responds slightly faster but may tear."},
    {"id": "internal_resolution", "section": "video", "key": "internal_resolution", "kind": "choice",
     "default": "4x",
     "choices": [["1x", "Original (1×)"], ["2x", "2×"], ["3x", "3× (≈ 720p)"], ["4x", "4× (≈ 1080p)"],
                 ["6x", "6× (≈ 1440p)"], ["8x", "8×"], ["9x", "9× (≈ 4K)"], ["display", "Match monitor"],
                 ["auto", "Automatic (dynamic)"]],
     "label": "Internal resolution", "group": "graphics",
     "help": "How sharply the 3D world is rendered. Higher is sharper and needs more GPU power."},
    {"id": "antialiasing_mode", "section": "video", "key": "antialiasing_mode", "kind": "choice",
     "default": "off", "choices": [["off", "Off"], ["fxaa", "FXAA"], ["fxaa_hq", "FXAA (high quality)"]],
     "label": "Antialiasing", "group": "graphics", "help": "Smooths jagged edges."},
    {"id": "texture_filtering", "section": "video", "key": "texture_filtering", "kind": "choice",
     "default": "nearest",
     "choices": [["nearest", "Original (sharp, pixelated)"], ["stable", "Smooth (3D world only)"],
                 ["bilinear", "Smooth (everything)"], ["xbr", "xBR (upscaled)"]],
     "label": "Textures", "group": "graphics",
     "help": "\"Smooth (3D world only)\" smooths the landscape but keeps text and menus sharp."},
    {"id": "pgxp", "section": "video", "key": ["geometry_correction", "perspective_texturing"],
     "kind": "bool", "default": False, "label": "Wobble fix (PGXP)", "group": "graphics",
     "help": "Removes the typical PS1 polygon wobble and warped textures."},
    {"id": "crt_filter", "section": "video", "key": "crt_filter", "kind": "choice", "default": "raw",
     "choices": [["raw", "Off (clean picture)"], ["crt", "CRT TV"], ["composite", "Composite cable"],
                 ["trinitron", "Trinitron"]],
     "label": "Retro screen", "group": "retro",
     "help": "Simulates how the game looked on a TV back then."},
    {"id": "scanlines", "section": "video", "key": "scanlines", "kind": "bool", "default": False,
     "label": "Scanlines", "group": "retro", "help": "Dark lines like on old TVs."},
    {"id": "volume", "section": "audio", "key": "volume", "kind": "int", "min": 0, "max": 100, "step": 5,
     "default": 100, "label": "Volume", "group": "sound", "help": ""},
]
SCHEMA_BY_ID = {s["id"]: s for s in SCHEMA}


def settings_path(game: Game) -> Path:
    from .builder import product_dir
    return product_dir(game) / "settings.toml"


def _load(game: Game) -> tomlkit.TOMLDocument:
    p = settings_path(game)
    if p.exists():
        try:
            return tomlkit.parse(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - a broken file is replaced, not fatal
            pass
    return tomlkit.document()


def _save(game: Game, doc: tomlkit.TOMLDocument) -> None:
    p = settings_path(game)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(tomlkit.dumps(doc), encoding="utf-8")
    tmp.replace(p)


def get_all(game: Game) -> dict[str, Any]:
    doc = _load(game)
    out = {}
    for s in SCHEMA:
        sec = doc.get(s["section"], {})
        keys = s["key"] if isinstance(s["key"], list) else [s["key"]]
        val = sec.get(keys[0], s["default"]) if hasattr(sec, "get") else s["default"]
        out[s["id"]] = _plain(val)
    return out


def set_value(game: Game, setting_id: str, value: Any) -> dict[str, Any]:
    s = SCHEMA_BY_ID[setting_id]
    value = _coerce(s, value)
    doc = _load(game)
    if s["section"] not in doc:
        doc[s["section"]] = tomlkit.table()
    keys = s["key"] if isinstance(s["key"], list) else [s["key"]]
    for k in keys:
        doc[s["section"]][k] = value
    _save(game, doc)
    return get_all(game)


def reset(game: Game) -> dict[str, Any]:
    doc = _load(game)
    for s in SCHEMA:
        if s["section"] in doc:
            for k in (s["key"] if isinstance(s["key"], list) else [s["key"]]):
                doc[s["section"]].pop(k, None)
    _save(game, doc)
    ensure_defaults(game, None, force=True)
    return get_all(game)


def ensure_defaults(game: Game, cue: str | None, force: bool = False) -> None:
    """First-install defaults: our own picks plus the disc location."""
    doc = _load(game)
    for sec in ("video", "audio", "launcher", "disc"):
        if sec not in doc:
            doc[sec] = tomlkit.table()
    for s in SCHEMA:
        for k in (s["key"] if isinstance(s["key"], list) else [s["key"]]):
            if force or k not in doc[s["section"]]:
                doc[s["section"]][k] = s["default"]
    # Our launcher replaces the per-game one; the game boots straight in.
    doc["launcher"]["skip_launcher"] = True
    if cue:
        doc["disc"]["path"] = cue
    _save(game, doc)


def disc_path(game: Game) -> str | None:
    doc = _load(game)
    d = doc.get("disc", {})
    return str(d.get("path")) if hasattr(d, "get") and d.get("path") else None


def _coerce(s: dict, value: Any) -> Any:
    if s["kind"] == "bool":
        return bool(value)
    if s["kind"] == "int":
        return max(s["min"], min(s["max"], int(value)))
    allowed = [c[0] for c in s["choices"]]
    for a in allowed:
        if str(a) == str(value):
            return a
    raise ValueError(f"Invalid value for {s['label']}: {value}")


def _plain(v: Any) -> Any:
    if hasattr(v, "unwrap"):
        return v.unwrap()
    return v
