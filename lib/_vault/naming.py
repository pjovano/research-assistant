from __future__ import annotations

import re
import unicodedata
from pathlib import Path

_CANONICAL_FORM = "NFC"

_ILLEGAL_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f]')

_SUBTITLE_SEPARATORS = (": ", " — ", " – ")

_BRACKET_PAIRS = {"(": ")", "[": "]", "{": "}"}

_LIBRARY_FILENAME_RE = re.compile(
    r"^(?P<creator>.+?) - (?P<year>\d{4}) - (?P<title>.+)\.pdf$", re.IGNORECASE)
_ET_AL_SUFFIX_RE = re.compile(r"\s+et al\.?$")
_CREATOR_JOINER_RE = re.compile(r"\s+and\s+")


class CreatorMissing(ValueError):
    def __init__(self) -> None:
        super().__init__("the record names no creator; a library filename needs at least one surname")


def nfc(text: str) -> str:
    return unicodedata.normalize(_CANONICAL_FORM, text)


def basename_of(path: Path) -> str:
    return nfc(path.stem)


def format_creator(surnames: list[str]) -> str:
    if not surnames:
        raise CreatorMissing()
    if len(surnames) == 1:
        return surnames[0]
    if len(surnames) == 2:
        return f"{surnames[0]} and {surnames[1]}"
    return f"{surnames[0]} et al."


def creator_surnames(creator: str) -> list[str]:
    named = _ET_AL_SUFFIX_RE.sub("", creator.strip())
    return [part.strip() for part in _CREATOR_JOINER_RE.split(named) if part.strip()]


def normalize_caps_name(name: str) -> str:
    if not name or any(c.islower() for c in name):
        return name
    return " ".join(_recase_shouted_word(word) for word in name.split())


def _recase_shouted_word(word: str) -> str:
    lowered = word.lower()
    capitalized = re.sub(r"(^|[\s'\-])(\w)",
                         lambda m: m.group(1) + m.group(2).upper(), lowered)
    return re.sub(r"^(Ma?c)([a-z])",
                  lambda m: m.group(1) + m.group(2).upper(), capitalized)


def sanitize_filename_part(text: str) -> str:
    return _ILLEGAL_FILENAME_CHARS.sub("", text).strip()


def strip_subtitle(title: str) -> str:
    for separator in _SUBTITLE_SEPARATORS:
        head, found, _ = title.partition(separator)
        if found and head.strip():
            return _close_brackets(head).strip() or title.strip()
    return title.strip()


def _close_brackets(head: str) -> str:
    unclosed = _unclosed_bracket_positions(head)
    return head[: unclosed[0]] if unclosed else head


def _unclosed_bracket_positions(head: str) -> list[int]:
    depth: list[int] = []
    for position, character in enumerate(head):
        if character in _BRACKET_PAIRS:
            depth.append(position)
        elif character in _BRACKET_PAIRS.values() and depth:
            depth.pop()
    return depth


def library_filename(surnames: list[str], year: str, title: str) -> str:
    creator = sanitize_filename_part(format_creator(surnames))
    return nfc(f"{creator} - {year} - {sanitize_filename_part(strip_subtitle(title))}.pdf")


library_filename_verbatim = library_filename


def parse_library_filename(name: str) -> dict | None:
    match = _LIBRARY_FILENAME_RE.match(name)
    if not match:
        return None
    return {"creator": match.group("creator"),
            "year": match.group("year"),
            "title": match.group("title")}
