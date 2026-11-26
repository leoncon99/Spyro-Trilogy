"""Static facts about the supported games and the pinned framework."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DiscVersion:
    region: str          # "PAL"
    serial: str          # "SCES-02104"
    bin_size: int
    bin_sha1: str
    needs_sbi: bool      # LibCrypt-protected pressing


@dataclass(frozen=True)
class Game:
    id: str              # "spyro1"
    number: int
    title: str
    subtitle: str
    year: int
    exe: str             # product executable basename (no .exe)
    kit: str             # folder under kits/
    versions: tuple = field(default_factory=tuple)


GAMES: tuple[Game, ...] = (
    Game("spyro1", 1, "Spyro the Dragon", "Das erste Abenteuer", 1998, "Spyro1", "spyro1",
         (DiscVersion("PAL", "SCES-01438", 732391632,
                      "52bba2f6a7eec6ac7dc4d08de13a01b0bbce30b6", False),)),
    Game("spyro2", 2, "Spyro 2: Gateway to Glimmer", "Ripto greift an", 1999, "Spyro2", "spyro2",
         (DiscVersion("PAL", "SCES-02104", 747300960,
                      "c394b2d061b7ea6f693275f92a622191db57c7e5", True),)),
    Game("spyro3", 3, "Spyro: Year of the Dragon", "Die gestohlenen Dracheneier", 2000, "Spyro3", "spyro3",
         (DiscVersion("PAL", "SCES-02835", 747418560,
                      "f1b46e4025b55d7a9791fd5a5fc5eadb167d723c", True),)),
)

GAMES_BY_ID = {g.id: g for g in GAMES}

# Framework sources, pinned. Downloaded once as GitHub source archives into
# the data folder; nothing of the games is ever downloaded.
FRAMEWORK = {
    "psxrecomp": ("mstan/psxrecomp", "d880ed91fc31f834769d7f5bf4b3b4b55df7c013", "psxrecomp"),
    "recomp-ui": ("RetroPortingToolKit/recomp-ui", "544c5c3a593951616d91e779c2fca62dcf683f80", "recomp-ui"),
    "recomp-net": ("RetroPortingToolKit/recomp-net", "c28e2391e2f2cb639c08b2ff24bb030248b8cd4f",
                   "psxrecomp/lib/recomp-net"),
    "rbengine": ("RetroPortingToolKit/rbengine", "28a2a472986a7d692d0378a22e756b0936413507",
                 "psxrecomp/lib/retcomm-rbengine"),
}
FRAMEWORK_STAMP = "-".join(v[1][:8] for v in FRAMEWORK.values())

# Python used to run the framework's build tools on Windows. The NuGet package
# is the official python.org build in a normal (non-embedded) layout, so
# scripts import their sibling modules as usual.
PYTHON_NUGET_URL = "https://www.nuget.org/api/v2/package/python/3.12.8"
