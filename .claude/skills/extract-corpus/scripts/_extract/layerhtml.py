from __future__ import annotations

import functools
import html
import re
import statistics
import unicodedata

from _extract.alphabets import lettered
from _extract.layerlines import RAISED_SIZE_SHARE, inked
from _extract.wordgaps import Gap, WordGaps, is_dash, is_overlay

RAISED_OFFSET_SHARE = 0.1
BOLD_TAG = "b"
ITALIC_TAG = "i"
SUPERSCRIPT_TAG = "sup"
SUBSCRIPT_TAG = "sub"
LINE_BREAK = "<br>"
LIGATURES = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"}
_SPACE_RUN_RE = re.compile(r" {2,}")
_SEAM_CLOSING_RE = re.compile(rf"</(?P<tag>{BOLD_TAG}|{ITALIC_TAG})>$")
_CLOSING_TAGS = r"(?:</\w+>)*"
_OPENING_TAGS = r"(?:<\w+>)*"
_SLASH_LINE_END_RE = re.compile(rf"\S/{_CLOSING_TAGS}$")
_WORD_LINE_START_RE = re.compile(rf"^{_OPENING_TAGS}\w")
_URL_LINE_END_RE = re.compile(rf"(?:://|www\.)[^\s<>]*{_CLOSING_TAGS}$", re.IGNORECASE)
_PATH_LINE_START_RE = re.compile(rf"^{_OPENING_TAGS}[^\s<>]*/")


class BlockHtml:
    def __init__(self, hyphens) -> None:
        self._hyphens = hyphens

    def of(self, rows: list[list]) -> str:
        return _SPACE_RUN_RE.sub(" ", self._flowed(self._written(rows))).strip()

    def stacked(self, rows: list[list]) -> str:
        return LINE_BREAK.join(self._written(rows))

    def _written(self, rows: list[list]) -> list[str]:
        written = [_Line(row).written().strip() for row in rows]
        return [line for line in written if line]

    def _flowed(self, lines: list[str]) -> str:
        joined = ""
        for line in lines:
            joined = self._joined(joined, line)
        return joined

    def _joined(self, text: str, line: str) -> str:
        if not text:
            return line
        text, line = _StyleSeam(text, line).bridged()
        if text.endswith("-"):
            return text + line if self._hyphens.keeps_hyphen(text, line) else text[:-1] + line
        return text + line if _breaks_a_slashed_token(text, line) else f"{text} {line}"


class _StyleSeam:
    def __init__(self, text: str, line: str) -> None:
        self._text = text
        self._line = line

    def bridged(self) -> tuple[str, str]:
        closing = _SEAM_CLOSING_RE.search(self._text)
        if closing is None or not self._line.startswith(f"<{closing.group('tag')}>"):
            return self._text, self._line
        opening_length = len(closing.group("tag")) + len("<>")
        return self._text[:closing.start()], self._line[opening_length:]


class _Line:
    def __init__(self, chars: list) -> None:
        self._chars = chars
        self._script = _ScriptHeight(chars)

    def written(self) -> str:
        pieces, held_overlays = [], ""
        tags = _Tags()
        for index, char in enumerate(self._chars):
            if _follows_its_base(char) and pieces:
                pieces[-1] += char.char
                continue
            if is_overlay(char):
                held_overlays += char.char
                continue
            piece = self._prose(tags, index)
            if held_overlays and not char.is_blank:
                piece, held_overlays = piece + held_overlays, ""
            pieces.append(piece)
        return unicodedata.normalize("NFC", "".join(pieces) + tags.closed())

    def _prose(self, tags: "_Tags", index: int) -> str:
        char = self._chars[index]
        if char.is_blank:
            return tags.spanning(" ")
        return tags.opened(self._tag_of(char), self._spacing(index)) + html.escape(_written(char), quote=False)

    def _tag_of(self, char) -> str | None:
        if self._script.raises(char):
            return SUPERSCRIPT_TAG
        if self._script.lowers(char):
            return SUBSCRIPT_TAG
        if char.bold:
            return BOLD_TAG
        return ITALIC_TAG if char.italic else None

    def _spacing(self, index: int) -> str:
        gap = self._gaps[index]
        return " " if gap is not None and self._word_gaps.opens_a_word(gap) else ""

    @functools.cached_property
    def _gaps(self) -> list[Gap | None]:
        return [self._gap_before(index) for index in range(len(self._chars))]

    @functools.cached_property
    def _word_gaps(self) -> WordGaps:
        return WordGaps(self._chars, [gap for gap in self._gaps if gap is not None])

    @functools.cached_property
    def _ink_before(self) -> "_InkBefore":
        return _InkBefore(self._chars)

    def _gap_before(self, index: int) -> Gap | None:
        previous = self._ink_before.ink(index)
        char = self._chars[index]
        if previous is None or char.is_blank or self._chars[index - 1].is_blank:
            return None
        width = char.bbox.left - self._ink_before.word_reach(index)
        return Gap(width, max(char.size, previous.size), index, is_dash(char) or is_dash(previous))


class _InkBefore:
    def __init__(self, chars: list) -> None:
        self._inks: list = []
        self._reaches: list[float | None] = []
        self._last_ink = None
        self._reach: float | None = None
        for char in chars:
            self._step(char)

    def ink(self, index: int):
        return self._inks[index]

    def word_reach(self, index: int) -> float:
        right = self._inks[index].bbox.right
        reach = self._reaches[index]
        return right if reach is None else max(right, reach)

    def _step(self, char) -> None:
        self._inks.append(self._last_ink)
        self._reaches.append(self._reach)
        if char.is_blank:
            self._reach = None
        elif not is_overlay(char):
            self._reach = char.bbox.right if self._reach is None else max(self._reach, char.bbox.right)
        if not is_overlay(char):
            self._last_ink = char


class _ScriptHeight:
    def __init__(self, chars: list) -> None:
        drawn = inked(chars)
        self._size = statistics.median([char.size for char in drawn]) if drawn else 0.0
        self._baseline = statistics.median([char.baseline for char in drawn]) if drawn else 0.0

    def raises(self, char) -> bool:
        return char.raised and self._is_small(char) and self._sits_above(char)

    def lowers(self, char) -> bool:
        is_a_letter_or_digit_in_the_column = char.char.isalnum() and not char.in_margin
        return is_a_letter_or_digit_in_the_column and self._is_small(char) and self._sits_below(char)

    def _is_small(self, char) -> bool:
        return char.size < RAISED_SIZE_SHARE * self._size

    def _sits_above(self, char) -> bool:
        return self._baseline - char.baseline > RAISED_OFFSET_SHARE * self._size

    def _sits_below(self, char) -> bool:
        return char.baseline - self._baseline > RAISED_OFFSET_SHARE * self._size


class _Tags:
    def __init__(self) -> None:
        self._open: str | None = None
        self._held = ""

    def opened(self, tag: str | None, spacing: str) -> str:
        if tag == self._open:
            return self._taken() + spacing
        closing = self._closing()
        self._open = tag
        return closing + self._taken() + spacing + (f"<{tag}>" if tag else "")

    def spanning(self, text: str) -> str:
        self._held += text
        return ""

    def closed(self) -> str:
        closing = self._closing()
        self._open = None
        return closing + self._taken()

    def _closing(self) -> str:
        return f"</{self._open}>" if self._open else ""

    def _taken(self) -> str:
        held, self._held = self._held, ""
        return held


def _breaks_a_slashed_token(text: str, line: str) -> bool:
    breaks_after_a_slash = _SLASH_LINE_END_RE.search(text) and _WORD_LINE_START_RE.match(line)
    breaks_a_url_path = _URL_LINE_END_RE.search(text) and _PATH_LINE_START_RE.match(line)
    return bool(breaks_after_a_slash or breaks_a_url_path)


def _follows_its_base(char) -> bool:
    return is_overlay(char) and char.bbox.width <= 0


def _written(char) -> str:
    return LIGATURES.get(char.char) or lettered(char.char, char.font)
