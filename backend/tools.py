"""Data folder layout and one-time downloads (Python, framework sources).

Nothing of the games is downloaded. The compiler pack is fetched by the
framework itself (`psxrecomp_cli.py ensure-toolchain`) into its shared cache.
"""
from __future__ import annotations

import io
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional

from .catalog import FRAMEWORK, FRAMEWORK_STAMP, PYTHON_NUGET_URL

IS_WINDOWS = os.name == "nt"
Progress = Callable[[float, str], None]


def data_dir() -> Path:
    override = os.environ.get("SPYRO_TRILOGY_HOME")
    if override:
        base = Path(override)
    elif IS_WINDOWS:
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "SpyroRecompTrilogy"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "SpyroRecompTrilogy"
    base.mkdir(parents=True, exist_ok=True)
    return base


def app_dir() -> Path:
    """Folder that holds ui/ and kits/ (PyInstaller unpack dir when frozen)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def framework_dir() -> Path:
    return data_dir() / "framework" / FRAMEWORK_STAMP


def python_exe() -> Path:
    if IS_WINDOWS:
        return data_dir() / "tools" / "python" / "tools" / "python.exe"
    return Path(shutil.which("python3") or sys.executable)


# ---------------------------------------------------------------- downloads

def _download(url: str, progress: Optional[Progress], label: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "SpyroRecompTrilogy-Setup"})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx, timeout=60) as r:
        total = int(r.headers.get("Content-Length") or 0)
        buf = io.BytesIO()
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            buf.write(chunk)
            if progress:
                frac = buf.tell() / total if total else 0.0
                mb = buf.tell() / 1e6
                progress(frac, f"{label} – {mb:.1f} MB")
        return buf.getvalue()


def _extract_github_zip(blob: bytes, dest: Path) -> None:
    """GitHub source zips have one top folder; strip it."""
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        names = z.namelist()
        top = names[0].split("/")[0] + "/"
        for info in z.infolist():
            if not info.filename.startswith(top):
                continue
            rel = info.filename[len(top):]
            if not rel:
                continue
            target = dest / rel
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
            mode = (info.external_attr >> 16) & 0o777
            if mode & 0o111 and not IS_WINDOWS:
                os.chmod(target, mode)


def ensure_python(progress: Optional[Progress] = None) -> Path:
    exe = python_exe()
    if not IS_WINDOWS or exe.exists():
        return exe
    dest = data_dir() / "tools" / "python"
    tmp = dest.with_name("python.partial")
    shutil.rmtree(tmp, ignore_errors=True)
    blob = _download(PYTHON_NUGET_URL, progress, "Python")
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        z.extractall(tmp)
    shutil.rmtree(dest, ignore_errors=True)
    tmp.rename(dest)
    return exe


def ensure_framework(progress: Optional[Progress] = None) -> Path:
    """Assemble psxrecomp + recomp-ui (+ psxrecomp submodules) at the pins."""
    from . import framework_patches
    root = framework_dir()
    marker = root / ".complete"
    if marker.exists():
        framework_patches.apply(root)   # also upgrades an already downloaded framework
        return root
    tmp = root.with_name(root.name + ".partial")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    local = os.environ.get("SPYRO_FRAMEWORK_SRC")  # developer/offline override
    items = list(FRAMEWORK.items())
    for i, (name, (repo, sha, rel)) in enumerate(items):
        dest = tmp / rel
        dest.mkdir(parents=True, exist_ok=True)
        base = i / len(items)

        def sub(frac: float, msg: str, base=base) -> None:
            if progress:
                progress(base + frac / len(items), msg)

        if local:
            src = Path(local) / rel
            shutil.copytree(src, dest, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns(".git", "build", "__pycache__"))
            sub(1.0, f"{name} kopiert")
        else:
            url = f"https://codeload.github.com/{repo}/zip/{sha}"
            blob = _download(url, sub, f"Framework: {name}")
            _extract_github_zip(blob, dest)
    framework_patches.apply(tmp)
    shutil.rmtree(root, ignore_errors=True)
    tmp.rename(root)
    marker.write_text(FRAMEWORK_STAMP)
    return root


def link_dir(target: Path, link: Path) -> None:
    """Directory link without admin rights: junction on Windows, symlink elsewhere."""
    if link.is_symlink() or link.exists():
        if link.is_symlink() or _is_junction(link):
            link.unlink() if link.is_symlink() else os.rmdir(link)
        else:
            shutil.rmtree(link)
    link.parent.mkdir(parents=True, exist_ok=True)
    if IS_WINDOWS:
        import _winapi
        _winapi.CreateJunction(str(target), str(link))
    else:
        link.symlink_to(target, target_is_directory=True)


def _is_junction(p: Path) -> bool:
    try:
        return bool(os.readlink(p)) and not p.is_symlink()
    except (OSError, ValueError):
        return False


def disk_free_gb(path: Path) -> float:
    return shutil.disk_usage(path).free / 1e9


def open_folder(path: Path) -> None:
    if IS_WINDOWS:
        os.startfile(str(path))  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", str(path)])
