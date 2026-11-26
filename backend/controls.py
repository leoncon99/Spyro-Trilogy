"""Keyboard and controller bindings, stored in the game's own INI files.

keybinds.ini  [player1]  <button> = <SDL key name>[, <second>]
input.ini     [mapping]  <button> = <SDL gamepad source>[, <second>]

Edits are line-based so the framework's comments and other sections stay
exactly as they are. Changes apply when the game starts next time.
"""
from __future__ import annotations

import re
from pathlib import Path

from .catalog import Game

BUTTONS = ["up", "down", "left", "right", "cross", "circle", "square", "triangle",
           "l1", "r1", "l2", "r2", "start", "select", "l3", "r3"]

KEY_DEFAULTS = {
    "up": "Up", "down": "Down", "left": "Left", "right": "Right", "cross": "X", "circle": "S",
    "square": "Z", "triangle": "A", "l1": "Q", "r1": "W", "l2": "E", "r2": "R", "l3": "T", "r3": "Y",
    "start": "Return", "select": "Right Shift",
}
PAD_DEFAULTS = {
    "up": "dpup", "down": "dpdown", "left": "dpleft", "right": "dpright", "cross": "a", "circle": "b",
    "square": "x", "triangle": "y", "l1": "leftshoulder", "r1": "rightshoulder", "l2": "lefttrigger",
    "r2": "righttrigger", "l3": "leftstick", "r3": "rightstick", "start": "start", "select": "back",
}

FILES = {"keys": ("keybinds.ini", "player1", KEY_DEFAULTS),
         "pad": ("input.ini", "mapping", PAD_DEFAULTS)}

_VALUE = re.compile(r"^[A-Za-z0-9 +\-/\[\]\\;',.=`]{1,40}$")


def _path(game: Game, device: str) -> Path:
    from .builder import product_dir
    return product_dir(game) / FILES[device][0]


def _read_section(text: str, section: str) -> dict[str, str]:
    out, cur = {}, None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("["):
            cur = line.strip("[] ").lower()
            continue
        if cur != section or not line or line[0] in ";#" or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip().lower()] = v.split(";")[0].strip() if not v.strip().startswith(";") else ""
    return out


def _write_value(text: str, section: str, key: str, value: str) -> str:
    lines = text.splitlines()
    cur, sec_end, found = None, None, False
    for i, raw in enumerate(lines):
        line = raw.strip()
        if line.startswith("["):
            if cur == section and sec_end is None:
                sec_end = i
            cur = line.strip("[] ").lower()
            continue
        if cur == section and "=" in line and line[0] not in ";#":
            k = line.split("=", 1)[0].strip().lower()
            if k == key:
                lines[i] = raw.split("=", 1)[0] + "= " + value   # keep the file's alignment
                found = True
                break
    if not found:
        if cur == section and sec_end is None:
            sec_end = len(lines)
        if sec_end is None:
            lines += ["", f"[{section}]"]
            sec_end = len(lines)
        lines.insert(sec_end, f"{key} = {value}")
    return "\n".join(lines) + "\n"


def get_all(game: Game) -> dict:
    out = {}
    for device, (_name, section, defaults) in FILES.items():
        p = _path(game, device)
        text = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
        cur = _read_section(text, section)
        out[device] = {b: cur.get(b, defaults[b]) for b in BUTTONS}
    return out


def set_binding(game: Game, device: str, button: str, value: str) -> dict:
    if device not in FILES or button not in BUTTONS:
        raise ValueError("unknown binding")
    value = (value or "None").strip()
    if not _VALUE.match(value):
        raise ValueError(f"invalid binding: {value}")
    _name, section, defaults = FILES[device]
    p = _path(game, device)
    text = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
    if section not in _read_section_names(text):
        # file (or section) not written by the game yet: start from the full defaults
        for b in BUTTONS:
            text = _write_value(text, section, b, defaults[b])
    p.write_text(_write_value(text, section, button, value), encoding="utf-8")
    return get_all(game)


def _read_section_names(text: str) -> set[str]:
    return {ln.strip().strip("[] ").lower() for ln in text.splitlines() if ln.strip().startswith("[")}


def reset(game: Game) -> dict:
    for device, (_name, section, defaults) in FILES.items():
        p = _path(game, device)
        text = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
        for b in BUTTONS:
            text = _write_value(text, section, b, defaults[b])
        p.write_text(text, encoding="utf-8")
    return get_all(game)
