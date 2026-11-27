"""The API the web UI calls (pywebview js_api, or HTTP in --serve mode)."""
from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Optional

from . import builder, controls, discs, settings, tools
from .catalog import GAMES, GAMES_BY_ID, KIT_STAMP

VERSION = "0.4.2"


class Api:
    def __init__(self) -> None:
        self._window = None                     # set by app.py (pywebview); private: pywebview walks public attributes
        self._runner = builder.BuildRunner(lambda snap: None)
        self._procs: dict[str, subprocess.Popen] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------- state
    def get_state(self) -> dict[str, Any]:
        installed = builder.load_installed()
        games = []
        for g in GAMES:
            info = installed.get(g.id)
            exe = builder.product_exe(g)
            ok = bool(info) and exe.exists()
            disc = settings.disc_path(g) if ok else None
            games.append({
                "id": g.id, "number": g.number, "title": g.title, "subtitle": g.subtitle, "year": g.year,
                "installed": ok,
                "info": info or None,
                "disc_missing": bool(ok and disc and not Path(disc).exists()),
                "outdated": bool(ok and info.get("kit") != KIT_STAMP),
                "running": self._is_running(g.id),
            })
        return {
            "version": VERSION,
            "games": games,
            "build": self._runner.snapshot(),
            "data_dir": str(tools.data_dir()),
            "free_gb": round(tools.disk_free_gb(tools.data_dir()), 1),
            "platform": "windows" if tools.IS_WINDOWS else "linux",
            "settings_schema": settings.SCHEMA,
        }

    # ------------------------------------------------------------ prefs
    def get_prefs(self) -> dict:
        import json
        try:
            return json.loads((tools.data_dir() / "app.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def set_pref(self, key: str, value: Any) -> dict:
        import json
        prefs = self.get_prefs()
        prefs[key] = value
        (tools.data_dir() / "app.json").write_text(json.dumps(prefs, indent=2), encoding="utf-8")
        return prefs

    # ------------------------------------------------------------- discs
    def pick_images(self) -> list[dict]:
        paths = self._file_dialog()
        return [discs.identify(p).to_dict() for p in paths]

    def pick_folder(self) -> list[dict]:
        folder = self._folder_dialog()
        if not folder:
            return []
        return [c.to_dict() for c in discs.scan_folder(folder)]

    def identify(self, path: str) -> dict:
        return discs.identify(path).to_dict()

    def scan(self, folder: str) -> list[dict]:
        return [c.to_dict() for c in discs.scan_folder(folder)]

    # ------------------------------------------------------------- build
    def start_build(self, selections: dict[str, str]) -> bool:
        sel = {k: v for k, v in selections.items() if k in GAMES_BY_ID and v}
        if not sel:
            return False
        return self._runner.start(sel)

    def cancel_build(self) -> None:
        self._runner.cancel()

    def build_log(self, game_id: str) -> str:
        p = builder.game_root(GAMES_BY_ID[game_id]) / "build.log"
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return text[-20000:]

    # ------------------------------------------------------------ games
    def launch(self, game_id: str) -> dict:
        g = GAMES_BY_ID[game_id]
        exe = builder.product_exe(g)
        if not exe.exists():
            return {"ok": False, "code": "launch.not_installed"}
        if self._is_running(game_id):
            return {"ok": False, "code": "launch.running"}
        disc = settings.disc_path(g)
        if disc and not Path(disc).exists():
            return {"ok": False, "code": "launch.disc_missing", "disc_missing": True}
        builder.migrate_saves(g)
        saves = builder.saves_dir(g)
        saves.mkdir(parents=True, exist_ok=True)
        self._spawn(game_id, [str(exe), "--no-launcher", "--memcard-dir", str(saves)], exe.parent,
                    bring_back=True)
        return {"ok": True}

    def open_advanced(self, game_id: str) -> dict:
        """The game's own detailed launcher (controls, hotkeys, mods …)."""
        g = GAMES_BY_ID[game_id]
        exe = builder.product_exe(g)
        if not exe.exists() or self._is_running(game_id):
            return {"ok": False}
        self._spawn(game_id, [str(exe), "--launcher"], exe.parent)
        return {"ok": True}

    def get_settings(self, game_id: str) -> dict:
        return settings.get_all(GAMES_BY_ID[game_id])

    def set_setting(self, game_id: str, setting_id: str, value: Any) -> dict:
        return settings.set_value(GAMES_BY_ID[game_id], setting_id, value)

    def apply_to_all(self, game_id: str) -> bool:
        src = settings.get_all(GAMES_BY_ID[game_id])
        for g in GAMES:
            if g.id != game_id and builder.product_exe(g).exists():
                for k, v in src.items():
                    settings.set_value(g, k, v)
        return True

    def get_controls(self, game_id: str) -> dict:
        return controls.get_all(GAMES_BY_ID[game_id])

    def set_control(self, game_id: str, device: str, button: str, value: str) -> dict:
        return controls.set_binding(GAMES_BY_ID[game_id], device, button, value)

    def reset_controls(self, game_id: str) -> dict:
        return controls.reset(GAMES_BY_ID[game_id])

    def controls_to_all(self, game_id: str) -> bool:
        src = controls.get_all(GAMES_BY_ID[game_id])
        for g in GAMES:
            if g.id != game_id and builder.product_exe(g).exists():
                for device, binds in src.items():
                    for button, value in binds.items():
                        controls.set_binding(g, device, button, value)
        return True

    def reset_settings(self, game_id: str) -> dict:
        return settings.reset(GAMES_BY_ID[game_id])

    def open_saves(self, game_id: str) -> None:
        g = GAMES_BY_ID[game_id]
        builder.migrate_saves(g)
        d = builder.saves_dir(g)
        d.mkdir(parents=True, exist_ok=True)
        tools.open_folder(d)

    def open_data_dir(self) -> None:
        tools.open_folder(tools.data_dir())

    def uninstall(self, game_id: str) -> bool:
        g = GAMES_BY_ID[game_id]
        if self._is_running(game_id) or self._runner.running:
            return False
        import shutil
        root = builder.game_root(g)
        builder.migrate_saves(g)
        saves = builder.saves_dir(g)
        backup = tools.data_dir() / "saves-backup" / g.id / time.strftime("%Y%m%d-%H%M%S")
        if saves.exists():
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(saves, backup)
        proj = builder.project_dir(g)
        for linked in ("psxrecomp", "recomp-ui"):
            lp = proj / linked
            if lp.is_symlink():
                lp.unlink()
            elif lp.exists() and tools.IS_WINDOWS:
                try:
                    os.rmdir(lp)
                except OSError:
                    pass
        shutil.rmtree(root, ignore_errors=True)
        data = builder.load_installed()
        data.pop(game_id, None)
        builder.save_installed(data)
        return True

    # ---------------------------------------------------------- helpers
    def _spawn(self, game_id: str, argv: list[str], cwd: Path, bring_back: bool = False) -> None:
        flags = 0
        if tools.IS_WINDOWS:
            flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        env = dict(os.environ)
        env["SPYRO_LANG"] = str(self.get_prefs().get("lang") or "")   # in-game menu language
        with self._lock:
            proc = subprocess.Popen(argv, cwd=cwd, creationflags=flags, env=env,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._procs[game_id] = proc
        if bring_back:
            threading.Thread(target=self._bring_back_after, args=(proc,), daemon=True).start()

    def _bring_back_after(self, proc: subprocess.Popen) -> None:
        """When the game closes (also via "Back to library"), show Spyro Trilogy again."""
        proc.wait()
        w = self._window
        if w is None:
            return
        try:
            w.restore()
            w.show()
            w.on_top = True      # raise above other windows once ...
            time.sleep(0.2)
            w.on_top = False     # ... without staying on top
        except Exception:  # noqa: BLE001 - cosmetic only
            pass

    def _is_running(self, game_id: str) -> bool:
        with self._lock:
            p = self._procs.get(game_id)
            return bool(p and p.poll() is None)

    def _file_dialog(self) -> list[str]:
        if self._window is None:
            return []
        import webview
        res = self._window.create_file_dialog(_dialog(webview, "OPEN"), allow_multiple=True,
                                             file_types=("PlayStation Image (*.cue)", "Alle Dateien (*.*)"))
        return list(res or [])

    def _folder_dialog(self) -> Optional[str]:
        if self._window is None:
            return None
        import webview
        res = self._window.create_file_dialog(_dialog(webview, "FOLDER"))
        return res[0] if res else None


def _dialog(webview, kind: str):
    """FileDialog.OPEN / .FOLDER (pywebview 5+), else the old constants."""
    fd = getattr(webview, "FileDialog", None)
    if fd is not None and hasattr(fd, kind):
        return getattr(fd, kind)
    return getattr(webview, f"{kind}_DIALOG")
