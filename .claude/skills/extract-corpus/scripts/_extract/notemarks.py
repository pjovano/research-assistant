from __future__ import annotations

import re

from _extract.notenumbers import NOTE_SYMBOLS, NUMBER_CLOSE

_RAISED_NUMBER = r"\d{1,3}"
_NOTE_LETTER = r"[a-z]"
_NOTE_SYMBOL = rf"[{NOTE_SYMBOLS}]+"
_NOTE_KEY = rf"{_NOTE_LETTER}|{_NOTE_SYMBOL}"
_WRITTEN_MARK = r"\[\^[^\]\s]+\]"

RAISED_RUN_RE = re.compile(rf"<sup>\s*({_RAISED_NUMBER}(?:\s*,\s*{_RAISED_NUMBER})*)\s*{NUMBER_CLOSE}\s*</sup>")
RAISED_NUMBER_RE = re.compile(rf"<sup>\s*({_RAISED_NUMBER})\s*</sup>")
RAISED_KEY_RE = re.compile(rf"<sup>\s*({_NOTE_KEY})\s*</sup>")
KEYED_NOTE_OPENING_RE = re.compile(
    rf"^\s*(?:<sup>\s*(?P<raised>{_NOTE_KEY})\s*</sup>|(?P<set>{_NOTE_SYMBOL})(?=\s))\s*")
WRITTEN_MARK_RE = re.compile(_WRITTEN_MARK)
SPACED_WRITTEN_MARK_RE = re.compile(rf"\s*{_WRITTEN_MARK}")


def raised_mark(number: str) -> str:
    return f"<sup>{number}</sup>"


def raised_mark_pattern(number: str) -> str:
    return rf"<sup>\s*{re.escape(number)}\s*{NUMBER_CLOSE}\s*</sup>"


def written_mark(label: int) -> str:
    return f"[^{label}]"


def note_key(opening: re.Match) -> str:
    return opening.group("raised") or opening.group("set")
