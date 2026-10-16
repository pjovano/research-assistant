from __future__ import annotations

import re

from _vault.markdown import WIKILINK_RE

UNCITABLE_TOKEN = "⚠ UNCITABLE-PDF"
UNCITABLE_FIELD = "uncitable"


SOURCE_TYPES = {
    "article": "a journal article, or a chapter filed as a book section",
    "monograph": "a book making one sustained argument",
    "historical": "a primary text in translation or in a critical edition",
    "textbook": "a textbook, handbook, companion, encyclopedia, or dictionary",
    "transcript": "a reviewed transcript of a recorded talk, paraphrased and never quoted",
}

SOURCE_ROLES = {
    "primary": "the text being commented on",
    "secondary": ("interpretation or criticism of a primary text; if it runs through one primary "
                  "work in that work's own order, it is a commentary and carries commentary_on"),
    "reference": "consulted for a fact or a definition, never argued with",
}

def wikilink_target(value: str) -> str | None:
    if not value:
        return None
    match = WIKILINK_RE.search(value)
    return match.group("target").strip() if match else None


def field_topics(meta: dict) -> list[str]:
    return [wikilink_target(field) or field for field in (meta.get("field") or [])]


def section_pattern(heading: str) -> re.Pattern:
    return re.compile(rf"(^## {re.escape(heading)}\n)(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)


def section_content(body: str, heading: str) -> str | None:
    hit = section_pattern(heading).search(body)
    return hit.group(2) if hit else None


def without_section(body: str, heading: str) -> str:
    return section_pattern(heading).sub("", body)


def commentary_target(meta: dict) -> str | None:
    return wikilink_target(str(meta.get("commentary_on") or ""))


BIBLIOGRAPHY_HEADING_RE = re.compile(
    r"\b(references|reference list|bibliography|bibliographie|bibliografia|works cited|literature cited"
    r"|literaturverzeichnis|literaturliste|quellenverzeichnis|(?:further|suggested|recommended) readings?)\b",
    re.IGNORECASE)
MAX_BIBLIOGRAPHY_HEADING_CHARS = 60
MAX_BIBLIOGRAPHY_HEADING_WORDS = 6
_HEADING_DECORATION = " .:*_#"


_NOTES_WORDS = r"endnotes|notes|anmerkungen|noten"
NOTES_HEADING_RE = re.compile(
    rf"^(?:(?:end)?note|{_NOTES_WORDS}|notes to (?:the )?(?:text|chapters?|pages))$", re.IGNORECASE)
NOTES_WORD_RE = re.compile(rf"\b(?:{_NOTES_WORDS})\b", re.IGNORECASE)


def is_notes_heading(title: str) -> bool:
    return NOTES_HEADING_RE.match(title.strip(_HEADING_DECORATION)) is not None


def names_notes_section(line: str) -> bool:
    return _is_short_heading_naming(line, NOTES_WORD_RE)


def is_bibliography_heading(title: str) -> bool:
    return _is_short_heading_naming(title, BIBLIOGRAPHY_HEADING_RE)


def _is_short_heading_naming(title: str, pattern: re.Pattern) -> bool:
    stripped = title.strip(_HEADING_DECORATION)
    if not stripped or len(stripped) > MAX_BIBLIOGRAPHY_HEADING_CHARS:
        return False
    if len(stripped.split()) > MAX_BIBLIOGRAPHY_HEADING_WORDS:
        return False
    return bool(pattern.search(stripped))
