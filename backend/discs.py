"""Recognise and verify the player's own disc images."""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable, Optional

from .catalog import GAMES, Game, DiscVersion

SECTOR = 2352


@dataclass
class DiscCheck:
    path: str                     # the .cue the player chose
    ok: bool
    game_id: Optional[str] = None
    title: Optional[str] = None
    region: Optional[str] = None
    serial: Optional[str] = None
    sbi: str = "none"             # none | ok | missing | invalid
    message: str = ""             # English, for logs
    code: str = ""                # translated by the UI (ui/i18n.js: msg.<code>)
    args: dict = None             # values for the message

    def fail(self, code: str, message: str, **args) -> "DiscCheck":
        self.ok, self.code, self.message, self.args = False, code, message, args
        return self

    def to_dict(self) -> dict:
        d = asdict(self)
        d["args"] = d["args"] or {}
        return d


def parse_cue(cue: Path) -> list[Path]:
    """Return the BINARY files a cue sheet references (absolute paths)."""
    files = []
    text = cue.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r'^\s*FILE\s+"?(.*?)"?\s+BINARY\s*$', text, re.M | re.I):
        files.append((cue.parent / m.group(1)).resolve())
    return files


def boot_serial(bin_path: Path) -> Optional[str]:
    """Read BOOT = cdrom:\\SCES_021.04 from SYSTEM.CNF via ISO9660."""
    try:
        with open(bin_path, "rb") as f:
            def sector(lba: int) -> bytes:
                f.seek(lba * SECTOR + 24)
                return f.read(2048)
            pvd = sector(16)
            if pvd[1:6] != b"CD001":
                return None
            root_lba = int.from_bytes(pvd[158:162], "little")
            root_size = int.from_bytes(pvd[166:170], "little")
            data = b"".join(sector(root_lba + i) for i in range((root_size + 2047) // 2048))
            pos = 0
            while pos < len(data):
                ln = data[pos]
                if ln == 0:
                    pos = (pos // 2048 + 1) * 2048
                    continue
                rec = data[pos:pos + ln]
                name = rec[33:33 + rec[32]].decode("ascii", "replace").split(";")[0]
                if name.upper() == "SYSTEM.CNF":
                    lba = int.from_bytes(rec[2:6], "little")
                    size = int.from_bytes(rec[10:14], "little")
                    cnf = sector(lba)[:size].decode("ascii", "replace")
                    m = re.search(r"BOOT\s*=\s*cdrom:\\?([A-Z]{4}_\d{3}\.\d{2})", cnf, re.I)
                    if m:
                        s = m.group(1).upper().replace("_", "-").replace(".", "")
                        return s
                    return None
                pos += ln
    except OSError:
        return None
    return None


def sbi_status(cue: Path) -> str:
    sbi = cue.with_suffix(".sbi")
    if not sbi.exists():
        alt = cue.with_suffix(".SBI")
        if not alt.exists():
            return "missing"
        sbi = alt
    data = sbi.read_bytes()
    if data[:4] != b"SBI\0" or (len(data) - 4) % 14 or len(data) == 4:
        return "invalid"
    for i in range(4, len(data), 14):
        rec = data[i:i + 14]
        if rec[3] != 1 or any((b >> 4) > 9 or (b & 15) > 9 for b in rec[:3]):
            return "invalid"
    return "ok"


def identify(cue_path: str) -> DiscCheck:
    """Quick check (no hashing): which game is this?"""
    cue = Path(cue_path)
    if cue.suffix.lower() != ".cue":
        return DiscCheck(cue_path, False).fail("disc.need_cue", "Please choose the image's .cue file.")
    if not cue.exists():
        return DiscCheck(cue_path, False).fail("disc.not_found", "File not found.")
    bins = parse_cue(cue)
    if len(bins) != 1:
        return DiscCheck(cue_path, False).fail("disc.format", "Unexpected image format (exactly one .bin expected).")
    if not bins[0].exists():
        return DiscCheck(cue_path, False).fail("disc.bin_missing", f"The .bin file is missing: {bins[0].name}", name=bins[0].name)
    serial = boot_serial(bins[0])
    for g in GAMES:
        for v in g.versions:
            if v.serial == serial:
                chk = DiscCheck(cue_path, True, g.id, g.title, v.region, v.serial)
                if v.needs_sbi:
                    chk.sbi = sbi_status(cue)
                return chk
    if serial:
        return DiscCheck(cue_path, False, serial=serial).fail(
            "disc.unsupported", f"This game ({serial}) is not supported.", serial=serial)
    return DiscCheck(cue_path, False).fail("disc.not_psx", "No PlayStation image detected.")


def verify(chk: DiscCheck, progress: Callable[[float], None] | None = None) -> DiscCheck:
    """Full check: size + SHA-1 of the data track against the known pressing."""
    if not chk.ok or not chk.game_id:
        return chk
    game: Game = next(g for g in GAMES if g.id == chk.game_id)
    version: DiscVersion = next(v for v in game.versions if v.serial == chk.serial)
    bin_path = parse_cue(Path(chk.path))[0]
    size = bin_path.stat().st_size
    if size != version.bin_size:
        return chk.fail("disc.size", "The image size differs from the known version (damaged or different dump).")
    h = hashlib.sha1()
    done = 0
    with open(bin_path, "rb") as f:
        while True:
            block = f.read(8 << 20)
            if not block:
                break
            h.update(block)
            done += len(block)
            if progress:
                progress(done / size)
    if h.hexdigest() != version.bin_sha1:
        return chk.fail("disc.hash", "Checksum mismatch: the image is damaged or a different version.")
    if version.needs_sbi and chk.sbi != "ok":
        return chk.fail("disc.sbi", "The .sbi file (copy-protection data) is missing or invalid. It must sit "
                        "next to the .cue with the same name.")
    chk.message, chk.code = "Image verified", "disc.verified"
    return chk


def scan_folder(folder: str, max_depth: int = 3) -> list[DiscCheck]:
    """Find supported .cue files in a folder (for 'Ordner durchsuchen')."""
    found = []
    base = Path(folder)
    for root, dirs, files in os.walk(base):
        depth = len(Path(root).relative_to(base).parts)
        if depth >= max_depth:
            dirs[:] = []
        for name in files:
            if name.lower().endswith(".cue"):
                chk = identify(str(Path(root) / name))
                if chk.game_id:
                    found.append(chk)
    return found
