from __future__ import annotations

import re
import unicodedata

COMBINING_FOR_SPACING = {
    "¨": "̈",
    "´": "́",
    "`": "̀",
    "ˆ": "̂",
    "˜": "̃",
    "ˇ": "̌",
    "˚": "̊",
    "˝": "̋",
    "¸": "̧",
    "¯": "̄",
    "˙": "̇",
}

DOTTED_FOR_DOTLESS = {"ı": "i", "ȷ": "j"}

_SPACING_ACCENTS = "".join(COMBINING_FOR_SPACING)
_PRECEDING_ACCENT_RE = re.compile("([" + _SPACING_ACCENTS + r"])([^\W\d_])")
_FOLLOWING_ACCENT_RE = re.compile(r"([^\W\d_])([" + _SPACING_ACCENTS + "])")


def composed(text: str) -> str:
    return _PRECEDING_ACCENT_RE.sub(_joined_after_accent, text)


def composed_either_side(text: str) -> str:
    return _FOLLOWING_ACCENT_RE.sub(_joined_before_accent, composed(text))


def _joined_after_accent(match: re.Match) -> str:
    spacing, letter = match.groups()
    return _composed_pair(letter, spacing) or match.group(0)


def _joined_before_accent(match: re.Match) -> str:
    letter, spacing = match.groups()
    return _composed_pair(letter, spacing) or match.group(0)


def _composed_pair(letter: str, spacing: str) -> str | None:
    base = DOTTED_FOR_DOTLESS.get(letter, letter)
    candidate = unicodedata.normalize("NFC", base + COMBINING_FOR_SPACING[spacing])
    return None if len(candidate) > 1 else candidate
