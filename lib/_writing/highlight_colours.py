from __future__ import annotations

import re
from dataclasses import dataclass

from _annotate.palette import TagPalette

CORE_COLOUR = "yellow"
CONTESTED_COLOUR = "orange"
POINTER_COLOUR = "gray"
THEORETICAL_COLOUR = "blue"
PRACTICAL_COLOUR = "green"
GROUP_COLOURS = (THEORETICAL_COLOUR, PRACTICAL_COLOUR)
POINTER_LINE_RE = re.compile(r"(?:Parallels:|Discussed in:).*|Cf\. [^:]*")
DISPUTE_LINE_RE = re.compile(r"Contra: .+")
CLAIM = "claim"
DISPUTE = "dispute"
POINTER = "pointer"


def kind_of(comment: str) -> str:
    lines = [line.strip() for line in comment.splitlines() if line.strip()]
    if any(DISPUTE_LINE_RE.fullmatch(line) for line in lines):
        return DISPUTE
    if lines and all(POINTER_LINE_RE.fullmatch(line) for line in lines):
        return POINTER
    return CLAIM


@dataclass(frozen=True)
class HighlightChoices:
    named: str | None = None
    core: tuple[str, ...] = ()
    group: str | None = None

    def __post_init__(self) -> None:
        if self.named is not None and TagPalette().named(self.named) is None:
            raise ValueError(f"unknown colour {self.named!r}; use one of {TagPalette().names}")
        if self.group is not None and self.group not in GROUP_COLOURS:
            raise ValueError(f"--group takes one of {list(GROUP_COLOURS)}, not {self.group!r}")

    def named_works(self) -> tuple[str, ...]:
        return self.core

    def colour_of(self, source: str, comment: str) -> str:
        if self.named is not None and source not in self.core:
            return self.named
        kind = kind_of(comment)
        if kind == DISPUTE:
            return CONTESTED_COLOUR
        if kind == POINTER:
            return POINTER_COLOUR
        return CORE_COLOUR if source in self.core else self._group()

    def _group(self) -> str:
        if self.group is None:
            raise ValueError(f"a claim comment outside the --generic works takes the note's group: "
                             f"pass --group, one of {list(GROUP_COLOURS)}")
        return self.group
