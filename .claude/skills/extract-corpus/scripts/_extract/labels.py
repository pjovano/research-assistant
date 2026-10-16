from __future__ import annotations

import re

from notation import DELIMITED_SPAN_RE

from _extract.notemarks import WRITTEN_MARK_RE as _FOOTNOTE_MARK_RE

_BARE_BRACKET_RE = re.compile(r"(?<!\\)[\[\]]")
_HOLD_MARK = "\x00"
_HELD_TEMPLATE = f"{_HOLD_MARK}{{index}}{_HOLD_MARK}"
_HELD_RE = re.compile(rf"{_HOLD_MARK}(\d+){_HOLD_MARK}")


class BracketedNotation:
    def resolved(self, text: str) -> str:
        held = _HeldSpans(text)
        return held.restored(_BARE_BRACKET_RE.sub(lambda bracket: f"\\{bracket.group(0)}", held.text))


class _HeldSpans:
    def __init__(self, text: str) -> None:
        self._spans: list[str] = []
        without_notation = DELIMITED_SPAN_RE.sub(self._held, text)
        self._text = _FOOTNOTE_MARK_RE.sub(self._held, without_notation)

    @property
    def text(self) -> str:
        return self._text

    def restored(self, text: str) -> str:
        return self._unheld(self._unheld(text))

    def _unheld(self, text: str) -> str:
        return _HELD_RE.sub(lambda match: self._spans[int(match.group(1))], text)

    def _held(self, match: re.Match) -> str:
        self._spans.append(match.group(0))
        return _HELD_TEMPLATE.format(index=len(self._spans) - 1)
