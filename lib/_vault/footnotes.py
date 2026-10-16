from __future__ import annotations

from _vault.markdown import FOOTNOTE_DEFINITION_RE, FOOTNOTE_MARK_RE


class FootnoteCallSites:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    def labels_defined_at(self, indices: list[int]) -> set[str]:
        return {self._label_of(index) for index in indices if self._label_of(index)}

    def indices_calling(self, labels: set[str]) -> list[int]:
        return [index for index, line in enumerate(self._lines) if self._calls_one_of(line, labels)]

    def _label_of(self, index: int) -> str | None:
        definition = FOOTNOTE_DEFINITION_RE.match(self._lines[index])
        return definition.group("label").strip()[2:-2].rstrip() if definition else None

    @staticmethod
    def _calls_one_of(line: str, labels: set[str]) -> bool:
        if FOOTNOTE_DEFINITION_RE.match(line):
            return False
        return any(mark.group("label") in labels for mark in FOOTNOTE_MARK_RE.finditer(line))
