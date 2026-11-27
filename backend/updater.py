"""Self-update from the project's GitHub releases.

Flow: check() asks the GitHub API for the latest release. install() downloads
the release ZIP and its .sha256 file, verifies the checksum, unpacks the app
into a staging folder and hands over to a small PowerShell script, which waits
for the app to exit, swaps the app folder and starts the new version.

Player data (games, saves, settings) lives in data_dir() and is never touched.
A release needs two assets: SpyroRecompTrilogy-<version>.zip and
SpyroRecompTrilogy-<version>.zip.sha256 (package.ps1 makes both).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import threading
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Optional

from . import tools

REPO = "leoncon99/Spyro-Recomp-Trilogy"
# Developer override (tests): base URL that serves /repos/<repo>/releases/latest
API_BASE = os.environ.get("SPYRO_UPDATE_API", "https://api.github.com").rstrip("/")
ASSET_RE = re.compile(r"^SpyroRecompTrilogy-(\d+(?:\.\d+)*)\.zip$")


def parse_version(v: str) -> tuple[int, ...]:
    m = re.search(r"(\d+(?:\.\d+)*)", v or "")
    return tuple(int(x) for x in m.group(1).split(".")) if m else ()


def is_frozen() -> bool:
    """Only the packaged EXE can replace itself."""
    return bool(getattr(sys, "frozen", False))


def install_dir() -> Path:
    return Path(sys.executable).resolve().parent


def _get(url: str, timeout: float = 15.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "SpyroRecompTrilogy-Updater",
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=timeout) as r:
        return r.read()


class Updater:
    def __init__(self, current: str) -> None:
        self.current = current
        self._lock = threading.Lock()
        self.state: dict[str, Any] = {"phase": "idle", "progress": 0.0, "error": None,
                                      "checked": False, "available": False, "info": None}
        self._apply: Optional[tuple[Path, Path, str]] = None

    # ------------------------------------------------------------ status
    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            s = dict(self.state)
        s["current"] = self.current
        s["can_install"] = is_frozen()
        return s

    def _set(self, **kw: Any) -> None:
        with self._lock:
            self.state.update(kw)

    # ------------------------------------------------------------- check
    def check(self) -> dict[str, Any]:
        if self.state["phase"] in ("downloading", "applying"):
            return self.snapshot()
        self._set(phase="checking", error=None)
        try:
            rel = json.loads(_get(f"{API_BASE}/repos/{REPO}/releases/latest"))
            tag = str(rel.get("tag_name") or "")
            version = ".".join(str(x) for x in parse_version(tag))
            assets = {a.get("name"): a for a in rel.get("assets") or []}
            zip_asset = next((a for n, a in assets.items() if n and ASSET_RE.match(n)), None)
            sha_asset = assets.get(zip_asset["name"] + ".sha256") if zip_asset else None
            newer = bool(version) and parse_version(version) > parse_version(self.current)
            info = {
                "version": version, "tag": tag, "name": rel.get("name") or tag,
                "notes": rel.get("body") or "", "url": rel.get("html_url") or "",
                "zip": zip_asset and zip_asset.get("browser_download_url"),
                "sha": sha_asset and sha_asset.get("browser_download_url"),
                "size": zip_asset and zip_asset.get("size"),
            }
            self._set(phase="idle", checked=True, available=newer, info=info)
        except Exception:  # noqa: BLE001 – offline, rate limit, private repo …
            self._set(phase="idle", checked=True, available=False, error="update.check_failed")
        return self.snapshot()

    # ----------------------------------------------------------- install
    def start_install(self) -> dict[str, Any]:
        s = self.snapshot()
        if not s["available"] or s["phase"] in ("downloading", "verifying", "applying"):
            return s
        self._set(phase="downloading", progress=0.0, error=None)   # visible at once
        threading.Thread(target=self._install, daemon=True).start()
        return self.snapshot()

    def _install(self) -> None:
        info = self.state["info"] or {}
        try:
            if not info.get("zip"):
                raise _Fail("update.no_asset")
            if not info.get("sha"):
                raise _Fail("update.no_checksum")
            work = tools.data_dir() / "update"
            shutil.rmtree(work, ignore_errors=True)
            work.mkdir(parents=True)

            self._set(phase="downloading", progress=0.0, error=None)
            blob = tools._download(info["zip"], lambda f, _l: self._set(progress=f * 0.9), "update")
            expected = _get(info["sha"]).decode("ascii", "replace").split()
            if not expected or hashlib.sha256(blob).hexdigest().lower() != expected[0].lower():
                raise _Fail("update.bad_checksum")

            self._set(phase="verifying", progress=0.92)
            staged = work / "app"
            exe_name = extract_app(blob, staged)   # may differ from ours after a rename
            self._set(progress=1.0)

            if not is_frozen():
                self._set(phase="ready", error="update.dev")   # running from source
                return
            target = install_dir()
            if not _writable(target.parent):
                raise _Fail("update.no_write")
            self._apply = (staged, target, exe_name)
            self._set(phase="ready")
        except _Fail as e:
            self._set(phase="error", error=e.code)
        except Exception:  # noqa: BLE001
            self._set(phase="error", error="update.download_failed")

    def apply_and_exit(self, window: Any) -> bool:
        """Start the swap script and close the app. Returns False if not ready."""
        if not self._apply or not tools.IS_WINDOWS:
            return False
        staged, target, exe_name = self._apply
        work = staged.parent
        script = work / "apply.ps1"
        script.write_text(APPLY_PS1, encoding="utf-8-sig")
        argv = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
                "-File", str(script), "-ProcId", str(os.getpid()), "-Src", str(staged),
                "-Dst", str(target), "-Exe", exe_name, "-Log", str(work / "update.log")]
        flags = 0x08000000 | 0x00000200   # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(argv, cwd=str(work), creationflags=flags, close_fds=True)
        self._set(phase="applying")
        if window is not None:
            threading.Timer(0.3, window.destroy).start()
        return True


class _Fail(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _writable(folder: Path) -> bool:
    probe = folder / ".spyro-update-probe"
    try:
        probe.write_text("x")
        probe.unlink()
        return True
    except OSError:
        return False


def extract_app(blob: bytes, dest: Path) -> str:
    """Unpack the release ZIP (one top folder, e.g. "Spyro Recomp Trilogy/") into dest.

    Windows' Compress-Archive may write backslashes as separators; both are
    accepted. Absolute paths and ".." are refused. Returns the EXE's name.
    """
    import io
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        entries = []
        for info in z.infolist():
            name = info.filename.replace("\\", "/")
            parts = [p for p in name.split("/") if p not in ("", ".")]
            if not parts or ".." in parts or re.match(r"^[A-Za-z]:", parts[0]) or name.startswith("/"):
                if parts:
                    raise _Fail("update.bad_package")
                continue
            entries.append((info, parts, name.endswith("/")))
        tops = {parts[0] for _, parts, _ in entries}
        if len(tops) != 1:
            raise _Fail("update.bad_package")
        exe = None
        for info, parts, is_dir in entries:
            rel = parts[1:]
            if not rel:
                continue
            target = dest.joinpath(*rel)
            if is_dir:
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
            if len(rel) == 1 and rel[0].lower().endswith(".exe"):
                exe = rel[0]
        if not exe or not (dest / "_internal").is_dir():
            raise _Fail("update.bad_package")
        return exe


# Waits for the app to exit, swaps the folder (rename old aside, copy new in),
# starts the new version. On failure it restores the old folder and starts it.
APPLY_PS1 = r'''param([int]$ProcId, [string]$Src, [string]$Dst, [string]$Exe, [string]$Log)
$ErrorActionPreference = "Stop"
function Say($m) { Add-Content -Path $Log -Value ("{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $m) }
$old = "$Dst.old"
$moved = $false
try {
    Say "waiting for process $ProcId"
    try { Wait-Process -Id $ProcId -Timeout 60 -ErrorAction SilentlyContinue } catch {}
    Start-Sleep -Milliseconds 700
    if (Test-Path -LiteralPath $old) { Remove-Item -LiteralPath $old -Recurse -Force }
    for ($i = 0; $i -lt 30 -and -not $moved; $i++) {
        try { Rename-Item -LiteralPath $Dst -NewName (Split-Path $old -Leaf); $moved = $true }
        catch { Start-Sleep -Milliseconds 500 }
    }
    if ($moved) {
        Copy-Item -LiteralPath $Src -Destination $Dst -Recurse -Force
        Say "installed into fresh folder"
    } else {
        # Folder busy (e.g. open in Explorer): overwrite the files in place.
        Copy-Item -Path (Join-Path $Src "*") -Destination $Dst -Recurse -Force
        Say "installed in place"
    }
    Start-Process -FilePath (Join-Path $Dst $Exe) -WorkingDirectory $Dst
    if ($moved) { Remove-Item -LiteralPath $old -Recurse -Force -ErrorAction SilentlyContinue }
    Remove-Item -LiteralPath $Src -Recurse -Force -ErrorAction SilentlyContinue
    Say "done"
} catch {
    Say "failed: $_"
    if ($moved -and (Test-Path -LiteralPath $old)) {
        if (Test-Path -LiteralPath $Dst) { Remove-Item -LiteralPath $Dst -Recurse -Force }
        Rename-Item -LiteralPath $old -NewName (Split-Path $Dst -Leaf)
        Say "restored previous version"
    }
    Start-Process -FilePath (Join-Path $Dst $Exe) -WorkingDirectory $Dst
}
'''
