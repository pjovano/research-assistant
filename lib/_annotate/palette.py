from __future__ import annotations

from dataclasses import dataclass

MAX_CHANNEL = 255
HEX_PREFIX = "#"

ZOTERO_COLOURS = (
    ("yellow", "#ffd400"),
    ("red", "#ff6666"),
    ("green", "#5fb236"),
    ("blue", "#2ea8e5"),
    ("purple", "#a28ae5"),
    ("magenta", "#e56eee"),
    ("orange", "#f19837"),
    ("gray", "#aaaaaa"),
)


@dataclass(frozen=True)
class Colour:
    name: str
    hex_code: str

    @property
    def rgb(self) -> tuple[float, float, float]:
        channels = bytes.fromhex(self.hex_code.removeprefix(HEX_PREFIX))
        return tuple(channel / MAX_CHANNEL for channel in channels)


class TagPalette:
    def __init__(self) -> None:
        self._colours = [Colour(name, code) for name, code in ZOTERO_COLOURS]

    @property
    def names(self) -> list[str]:
        return [colour.name for colour in self._colours]

    def named(self, name: str) -> Colour | None:
        wanted = name.strip().lower()
        return next((c for c in self._colours if c.name == wanted), None)
