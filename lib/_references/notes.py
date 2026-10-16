from __future__ import annotations

import vault

HEADING_RE = vault.HEADING_RE
DEFINITION_RE = vault.FOOTNOTE_DEFINITION_RE


class NoteLines:
    def __init__(self, body: str) -> None:
        self._lines = body.split("\n")

    @property
    def lines(self) -> list[str]:
        return list(self._lines)

    def entry_indices(self) -> list[int]:
        return sorted(self._listed_indices() | self._definition_indices())

    def _listed_indices(self) -> set[int]:
        return {index for heading, end in vault.EntryListSpans(self._lines).all() for index in range(heading + 1, end)}

    def _definition_indices(self) -> set[int]:
        return {index for index, line in enumerate(self._lines) if DEFINITION_RE.match(line)}
