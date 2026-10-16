from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from notation import blanked_notation
from page_marker import PageMarker
from vault import CITATION_LINK_MARK, FOOTNOTE_DEFINITION_RE, HEADING_RE, OBSIDIAN_COMMENT_RE, WIKILINK_RE

HEADING_PATH_SEPARATOR = " > "
LINE_JOIN = "\n"
TABLE_LINE_PREFIX = "|"
DISPLAY_MATH_DELIMITER = "$$"
COMMENT_REPLACEMENT = " "

_FOOTNOTE_MARK_RE = re.compile(r"\[\^[^\]]+\](?!:)")
_IMAGE_RE = re.compile(r"!\[(?P<alt>[^\]]*)\]\([^)]*\)")
_HTML_TABLE_LINE_RE = re.compile(r"^\s*</?(?:table|thead|tbody|tfoot|tr)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Heading:
    level: int
    text: str

    @staticmethod
    def parsed(line: str) -> "Heading | None":
        match = HEADING_RE.match(line)
        if match is None:
            return None
        return Heading(len(match.group("hashes")), InlineMarkup.cleaned(match.group("text")))


class LineKind(Enum):
    HEADING = "heading"
    PAGE_MARKER = "page marker"
    BLANK = "blank"
    FOOTNOTE_DEFINITION = "footnote definition"
    DISPLAY_MATH_DELIMITER = "display math delimiter"
    TABLE = "table"
    PROSE = "prose"


def line_kind(line: str) -> LineKind:
    if Heading.parsed(line) is not None:
        return LineKind.HEADING
    if PageMarker.parsed(line) is not None:
        return LineKind.PAGE_MARKER
    if not line.strip():
        return LineKind.BLANK
    if is_footnote_definition(line):
        return LineKind.FOOTNOTE_DEFINITION
    if is_display_math_delimiter(line):
        return LineKind.DISPLAY_MATH_DELIMITER
    if is_table_line(line):
        return LineKind.TABLE
    return LineKind.PROSE


def is_table_line(line: str) -> bool:
    return line.startswith(TABLE_LINE_PREFIX) or _HTML_TABLE_LINE_RE.match(line) is not None


def is_footnote_definition(line: str) -> bool:
    return FOOTNOTE_DEFINITION_RE.match(line) is not None


def is_display_math_delimiter(line: str) -> bool:
    return line.count(DISPLAY_MATH_DELIMITER) % 2 == 1


class InlineMarkup:
    @staticmethod
    def cleaned(text: str) -> str:
        uncommented = OBSIDIAN_COMMENT_RE.sub(COMMENT_REPLACEMENT, text)
        shown = InlineMarkup._links_shown(uncommented)
        captioned = _IMAGE_RE.sub(_image_alt, shown)
        unmarked = _FOOTNOTE_MARK_RE.sub("", captioned)
        return LINE_JOIN.join(line.strip() for line in unmarked.splitlines())

    @staticmethod
    def _links_shown(text: str) -> str:
        pieces, cursor = [], 0
        for match in WIKILINK_RE.finditer(blanked_notation(text)):
            pieces += [text[cursor:match.start()], _wikilink_shown(match)]
            cursor = match.end()
        return "".join(pieces) + text[cursor:]


def _wikilink_shown(match: re.Match) -> str:
    if match.group("shown") == CITATION_LINK_MARK:
        return ""
    return match.group("shown") or match.group("target")


def _image_alt(match: re.Match) -> str:
    return match.group("alt")
