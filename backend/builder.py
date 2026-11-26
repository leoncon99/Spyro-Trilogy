"""Build pipeline: own disc image -> native game, on the player's machine."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from . import discs, tools
from .catalog import GAMES_BY_ID, KIT_STAMP, Game

NINJA_RE = re.compile(r"^\[(\d+)/(\d+)\]")

# Share of the whole job per stage (sums to 1).
STAGES = [
    ("verify", "Image prüfen", 0.06),
    ("prepare", "Projekt vorbereiten", 0.02),
    ("generate", "Spielcode übersetzen", 0.37),
    ("build", "Kompilieren", 0.52),
    ("install", "Fertigstellen", 0.03),
]


@dataclass
class JobState:
    game_id: str
    stage: str = "queued"
    progress: float = 0.0          # whole job 0..1
    detail: str = ""               # code, translated by the UI (msg.<code>)
    detail_args: dict = field(default_factory=dict)
    status: str = "queued"         # queued | running | done | error | cancelled
    error: str = ""                # code (msg.<code>) or raw text
    error_args: dict = field(default_factory=dict)
    log_tail: list = field(default_factory=list)

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["log_tail"] = self.log_tail[-12:]
        return d


def game_root(game: Game) -> Path:
    return tools.data_dir() / "games" / game.id


def project_dir(game: Game) -> Path:
    return game_root(game) / "project"


def product_dir(game: Game) -> Path:
    return project_dir(game) / "build-release"


def product_exe(game: Game) -> Path:
    return product_dir(game) / (game.exe + (".exe" if tools.IS_WINDOWS else ""))


def state_file() -> Path:
    return tools.data_dir() / "installed.json"


def load_installed() -> dict:
    try:
        return json.loads(state_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_installed(data: dict) -> None:
    tmp = state_file().with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(state_file())


class BuildError(Exception):
    def __init__(self, code: str, text: str = "", **args):
        super().__init__(text or code)
        self.code, self.args = code, args


class BuildRunner:
    """Runs one queue of game builds on a worker thread."""

    def __init__(self, on_update: Callable[[dict], None]):
        self.on_update = on_update
        self.jobs: dict[str, JobState] = {}
        self.order: list[str] = []
        self.global_stage = ""        # tools step code (msg.<code>)
        self.global_args: dict = {}
        self.global_progress = 0.0
        self.running = False
        self._cancel = False
        self._proc: Optional[subprocess.Popen] = None
        self.toolchain_bin = ""
        self._lock = threading.Lock()

    # ------------------------------------------------------------ public
    def snapshot(self) -> dict:
        with self._lock:
            return {
                "running": self.running,
                "tools": {"code": self.global_stage, "args": self.global_args, "progress": self.global_progress},
                "jobs": [self.jobs[g].to_dict() for g in self.order],
            }

    def start(self, selections: dict[str, str]) -> bool:
        """selections: game_id -> path of the player's .cue"""
        if self.running:
            return False
        self._cancel = False
        self.jobs = {g: JobState(g) for g in selections}
        self.order = [g for g in ("spyro1", "spyro2", "spyro3") if g in selections]
        self.running = True
        threading.Thread(target=self._run, args=(dict(selections),), daemon=True).start()
        return True

    def cancel(self) -> None:
        self._cancel = True
        p = self._proc
        if p and p.poll() is None:
            try:
                p.terminate()
            except OSError:
                pass

    # ----------------------------------------------------------- internal
    def _emit(self) -> None:
        try:
            self.on_update(self.snapshot())
        except Exception:
            pass

    def _set(self, job: JobState, stage: str, frac: float, detail: str = "", **args) -> None:
        offset = 0.0
        for key, _label, share in STAGES:
            if key == stage:
                with self._lock:
                    job.stage = key
                    job.progress = min(1.0, offset + share * max(0.0, min(1.0, frac)))
                    if detail:
                        job.detail, job.detail_args = detail, args
                break
            offset += share
        self._emit()

    def _log(self, job: JobState, line: str) -> None:
        line = line.rstrip()
        if line:
            with self._lock:
                job.log_tail.append(line[:300])
                del job.log_tail[:-60]
            log = game_root(GAMES_BY_ID[job.game_id]) / "build.log"
            with open(log, "a", encoding="utf-8", errors="replace") as f:
                f.write(line + "\n")

    def _run(self, selections: dict[str, str]) -> None:
        try:
            self._prepare_tools()
        except Exception as e:  # noqa: BLE001
            for job in self.jobs.values():
                job.status, job.error, job.error_args = "error", "err.tools", {"detail": str(e)}
            self.running = False
            self._emit()
            return
        for gid in self.order:
            job = self.jobs[gid]
            if self._cancel:
                job.status = "cancelled"
                continue
            job.status = "running"
            try:
                self._build_one(GAMES_BY_ID[gid], selections[gid], job)
                job.status, job.progress, job.detail = "done", 1.0, ""
            except _Cancelled:
                job.status = "cancelled"
            except BuildError as e:
                job.status, job.error, job.error_args = "error", e.code, e.args
                self._log(job, f"ERROR: {e}")
            except Exception as e:  # noqa: BLE001
                job.status, job.error, job.error_args = "error", "err.raw", {"detail": str(e)}
                self._log(job, f"ERROR: {e}")
            self._emit()
        self.running = False
        self._emit()

    def _prepare_tools(self) -> None:
        def prog(base: float, share: float):
            def f(frac: float, msg: str) -> None:
                self.global_progress = base + share * frac
                self.global_stage, self.global_args = "tools.download", {"what": msg}
                self._emit()
            return f
        self.global_stage, self.global_args = "tools.check", {}
        self._emit()
        tools.ensure_python(prog(0.0, 0.15))
        fw = tools.ensure_framework(prog(0.15, 0.35))
        if tools.IS_WINDOWS and not os.environ.get("SPYRO_NO_TOOLCHAIN_DOWNLOAD"):
            self.global_progress, self.global_stage, self.global_args = 0.5, "tools.compiler", {}
            self._emit()
            self.toolchain_bin = self._ensure_toolchain(fw)
        self.global_progress, self.global_stage, self.global_args = 1.0, "tools.ready", {}
        self._emit()

    def _ensure_toolchain(self, fw: Path) -> str:
        """cmake-clang pack into the framework's shared cache; returns its bin dir."""
        work = tools.data_dir() / "tools"
        work.mkdir(parents=True, exist_ok=True)
        argv = [str(tools.python_exe()), str(fw / "psxrecomp" / "psxrecomp_cli.py"), "ensure-toolchain",
                "--project-root", str(work), "--json-progress"]
        out = subprocess.run(argv, cwd=work, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", creationflags=0x08000000 if tools.IS_WINDOWS else 0)
        bin_dir = ""
        for line in out.stdout.splitlines():
            s = line.strip()
            if s.startswith("{") and '"result"' in s:
                try:
                    bin_dir = json.loads(s).get("toolchain_bin", "") or bin_dir
                except ValueError:
                    pass
        if out.returncode != 0 or not bin_dir:
            tail = "\n".join((out.stdout + out.stderr).splitlines()[-8:])
            raise BuildError("err.compiler", tail, detail=tail)
        return bin_dir

    # ---------------------------------------------------------- one game
    def _build_one(self, game: Game, cue: str, job: JobState) -> None:
        root = game_root(game)
        root.mkdir(parents=True, exist_ok=True)
        (root / "build.log").write_text(f"Build {game.title} {time.ctime()}\n", encoding="utf-8")

        # 1. verify
        self._set(job, "verify", 0.0, "d.hashing")
        chk = discs.identify(cue)
        if chk.game_id != game.id:
            raise BuildError("msg." + chk.code if chk.code else "err.wrong_game", chk.message, **(chk.args or {}))
        chk = discs.verify(chk, lambda f: self._set(job, "verify", f))
        if not chk.ok:
            raise BuildError("msg." + chk.code, chk.message, **(chk.args or {}))
        self._check_cancel()

        # 2. project folder: kit + linked framework; keep saves/settings
        self._set(job, "prepare", 0.0, "d.project")
        proj = project_dir(game)
        keep = self._stash_player_files(game)
        if proj.exists():
            for linked in ("psxrecomp", "recomp-ui"):   # never recurse into the shared framework
                lp = proj / linked
                if lp.is_symlink():
                    lp.unlink()
                elif lp.exists() and tools.IS_WINDOWS:
                    try:
                        os.rmdir(lp)                    # removes a junction, not its target
                    except OSError:
                        pass
            shutil.rmtree(proj, onerror=_force_remove)
        shutil.copytree(tools.app_dir() / "kits" / game.kit, proj)
        fw = tools.framework_dir()
        tools.link_dir(fw / "psxrecomp", proj / "psxrecomp")
        tools.link_dir(fw / "recomp-ui", proj / "recomp-ui")
        toml = proj / "game.toml"
        toml.write_text(toml.read_text(encoding="utf-8").replace("@DISC@", Path(cue).as_posix()),
                        encoding="utf-8")
        self._set(job, "prepare", 1.0)
        self._check_cancel()

        py = str(tools.python_exe())
        cli = str(proj / "psxrecomp" / "psxrecomp_cli.py")

        # 3. generate (framework emitters + game C)
        self._set(job, "generate", 0.0, "d.recompiler")
        self._run_cli(job, "generate",
                      [py, cli, "generate", "--config", "game.toml", "--project-root", ".",
                       "--disc", cue, "--json-progress"], proj)

        # 4. build
        self._set(job, "build", 0.0, "d.configure")
        extra = [f"--cmake-extra={a}" for a in os.environ.get("SPYRO_CMAKE_EXTRA", "").split() if a]
        nodl = ["--no-toolchain-download"] if os.environ.get("SPYRO_NO_TOOLCHAIN_DOWNLOAD") else []
        self._run_cli(job, "build",
                      [py, cli, "rebuild", "--config", "game.toml", "--project-root", ".",
                       "--build-dir", "build-release", "--no-pgo", "--json-progress",
                       "--prune-after", "build-intermediates", *nodl, *extra], proj)
        exe = product_exe(game)
        if not exe.exists():
            raise BuildError("err.no_exe")

        # 5. install: tidy, restore player files, defaults, record
        self._set(job, "install", 0.2, "d.cleanup")
        for big in (proj / "disc").glob("*.bin"):
            big.unlink(missing_ok=True)
        self._restore_player_files(game, keep)
        from . import settings as st
        st.ensure_defaults(game, cue)
        data = load_installed()
        data[game.id] = {"cue": cue, "serial": chk.serial, "region": chk.region,
                         "built": time.strftime("%Y-%m-%d %H:%M"), "framework": tools.FRAMEWORK_STAMP,
                         "kit": KIT_STAMP}
        save_installed(data)
        self._set(job, "install", 1.0)

    def _run_cli(self, job: JobState, stage: str, argv: list[str], cwd: Path) -> None:
        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        if self.toolchain_bin:
            # The toolchain's own DLLs must win over e.g. Git's (WINDOWS_TOOLCHAIN_TRAPS.md).
            env["PATH"] = self.toolchain_bin + os.pathsep + env.get("PATH", "")
            env["PSXRECOMP_TOOLCHAIN_DIR"] = str(Path(self.toolchain_bin).parent)
        flags = 0x08000000 if tools.IS_WINDOWS else 0  # CREATE_NO_WINDOW
        self._log(job, "$ " + " ".join(argv))
        self._proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                      errors="replace", bufsize=1, creationflags=flags)
        last_ok = None
        watcher = None
        if stage == "build":
            watcher = threading.Thread(target=self._watch_objects, args=(job, cwd / "build-release"), daemon=True)
            self._watching = True
            watcher.start()
        for line in self._proc.stdout:  # type: ignore[union-attr]
            if self._cancel:
                break
            self._log(job, line)
            s = line.strip()
            if s.startswith("{") and s.endswith("}"):
                try:
                    ev = json.loads(s)
                except ValueError:
                    continue
                if ev.get("event") == "phase":
                    pct = float(ev.get("pct") or 0.0)
                    self._set(job, stage, pct * (0.9 if stage == "build" else 1.0),
                              _friendly(ev.get("message", "")), text=ev.get("message", "")[:80])
                elif ev.get("event") == "result":
                    last_ok = bool(ev.get("ok"))
                continue
            m = NINJA_RE.match(s)
            if m and stage == "build":
                done, total = int(m.group(1)), int(m.group(2))
                if total > 50:  # the game build, not small helper builds
                    self._set(job, stage, 0.1 + 0.85 * done / total, "d.files", n=done, total=total)
        rc = self._proc.wait()
        self._proc = None
        self._watching = False
        self._check_cancel()
        if rc != 0 or last_ok is False:
            raise BuildError("err.step", stage=stage, rc=rc)

    def _watch_objects(self, job: JobState, build_dir: Path, expected: int = 830) -> None:
        """cmake --build output arrives only at the end; count finished objects instead."""
        best = 0.0
        while getattr(self, "_watching", False):
            time.sleep(2.0)
            n = 0
            try:
                for _root, _dirs, files in os.walk(build_dir / "CMakeFiles"):
                    n += sum(1 for f in files if f.endswith((".o", ".obj")))
            except OSError:
                continue
            frac = 0.1 + 0.85 * min(1.0, n / expected)
            if frac > best and getattr(self, "_watching", False):
                best = frac
                self._set(job, "build", frac, "d.files_approx", n=min(n, expected), total=expected)

    def _check_cancel(self) -> None:
        if self._cancel:
            raise _Cancelled()

    def _stash_player_files(self, game: Game) -> Path:
        """Move saves/settings out of the way while the project is rebuilt."""
        keep = game_root(game) / "keep"
        prod = product_dir(game)
        for name in ("saves", "settings.toml", "keybinds.ini", "input.ini", "config.ini", "mods/state.toml",
                     "mods/installed"):
            src = prod / name
            if src.exists():
                dst = keep / name
                dst.parent.mkdir(parents=True, exist_ok=True)
                if dst.exists():
                    shutil.rmtree(dst) if dst.is_dir() else dst.unlink()
                shutil.move(str(src), str(dst))
        return keep

    def _restore_player_files(self, game: Game, keep: Path) -> None:
        if not keep.exists():
            return
        prod = product_dir(game)
        for src in sorted(keep.rglob("*"), key=lambda p: len(p.parts)):
            rel = src.relative_to(keep)
            dst = prod / rel
            if src.is_dir():
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        shutil.rmtree(keep, ignore_errors=True)


class _Cancelled(Exception):
    pass


def _force_remove(func, path, _exc):
    try:
        os.chmod(path, 0o700)
        func(path)
    except OSError:
        pass


def _friendly(msg: str) -> str:
    """Framework phase text -> UI message code (msg.<code>); unknown -> d.raw."""
    table = [
        ("Building psxrecomp", "d.recompiler"),
        ("Checking disc", "d.disc"),
        ("Normalizing disc", "d.prepare_disc"),
        ("emitter", "d.recompiler"),
        ("OpenBIOS", "d.bios"),
        ("Recompil", "d.translate"),
        ("Generate complete", "d.translated"),
        ("toolchain", "d.compiler"),
        ("cmake", "d.compile"),
        ("PGO", "d.optimize"),
        ("Staging", "d.staging"),
        ("Rebuild complete", "d.built"),
    ]
    for key, code in table:
        if key.lower() in msg.lower():
            return code
    return "d.raw"
