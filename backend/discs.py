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
    message: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


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
        return DiscCheck(cue_path, False, message="Bitte die .cue-Datei des Images wählen.")
    if not cue.exists():
        return DiscCheck(cue_path, False, message="Datei nicht gefunden.")
    bins = parse_cue(cue)
    if len(bins) != 1:
        return DiscCheck(cue_path, False, message="Unerwartetes Image-Format (genau eine .bin erwartet).")
    if not bins[0].exists():
        return DiscCheck(cue_path, False, message=f"Die .bin-Datei fehlt: {bins[0].name}")
    serial = boot_serial(bins[0])
    for g in GAMES:
        for v in g.versions:
            if v.serial == serial:
                chk = DiscCheck(cue_path, True, g.id, g.title, v.region, v.serial)
                if v.needs_sbi:
                    chk.sbi = sbi_status(cue)
                return chk
    if serial:
        return DiscCheck(cue_path, False, serial=serial,
                         message=f"Dieses Spiel ({serial}) wird nicht unterstützt.")
    return DiscCheck(cue_path, False, message="Kein PlayStation-Image erkannt.")


def verify(chk: DiscCheck, progress: Callable[[float], None] | None = None) -> DiscCheck:
    """Full check: size + SHA-1 of the data track against the known pressing."""
    if not chk.ok or not chk.game_id:
        return chk
    game: Game = next(g for g in GAMES if g.id == chk.game_id)
    version: DiscVersion = next(v for v in game.versions if v.serial == chk.serial)
    bin_path = parse_cue(Path(chk.path))[0]
    size = bin_path.stat().st_size
    if size != version.bin_size:
        chk.ok = False
        chk.message = "Das Image hat eine andere Größe als die bekannte Version (beschädigt oder anderer Dump)."
        return chk
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
        chk.ok = False
        chk.message = "Prüfsumme stimmt nicht – das Image ist beschädigt oder eine andere Version."
        return chk
    if version.needs_sbi and chk.sbi != "ok":
        chk.ok = False
        chk.message = ("Die .sbi-Datei (Kopierschutzdaten) fehlt oder ist ungültig. Sie muss neben der .cue "
                       "liegen und denselben Namen haben.")
        return chk
    chk.message = "Image geprüft"
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
