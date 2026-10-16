from __future__ import annotations

import re
from dataclasses import dataclass

YEAR_PATTERN = r"(1[4-9]\d\d|20\d\d)"
YEAR_RE = re.compile(rf"\b{YEAR_PATTERN}[a-z]?\b")

_REPEAT_AUTHOR_RE = re.compile(rf"^\s*(?:[-—–_]{{2,}}\s*|(?=(?:eds?\.\s+)?\(?{YEAR_PATTERN}[a-z]?\)?[.,:]))")

_ENTRY_OPENING_RE = re.compile(
    r"^\s*(?:\[\d{1,3}\]|\d{1,3}\.)?\s*"
    r"(?:van |de |von |der |di |du |le |la )?"
    r"[^\W\d_][^\W\d_'’.-]*,\s+[^\W\d_]", re.UNICODE | re.IGNORECASE)

_SURNAME_RE = re.compile(r"([^\W\d_][^\W\d_'’-]{1,})\s*,", re.UNICODE)

MIN_ENTRY_CHARS = 20

MAX_ENTRY_CHARS = 600

MAX_HEAD_CHARS = 120

_HEAD_TRAILING = " ([,;."


@dataclass(frozen=True)
class ReferenceEntry:
    raw: str
    surnames: tuple[str, ...]
    year: str | None


class RepeatedAuthors:
    def __init__(self) -> None:
        self._head = ""

    def restored(self, entry: str) -> str:
        repeated = _REPEAT_AUTHOR_RE.match(entry)
        if repeated is None:
            self._head = self._head_of(entry)
            return entry
        return f"{self._head}{entry[repeated.end():]}" if self._head else entry

    @staticmethod
    def _head_of(entry: str) -> str:
        year = YEAR_RE.search(entry)
        head = (entry[:year.start()] if year else "").rstrip(_HEAD_TRAILING)
        return f"{head} " if head else ""


class EntryParser:
    def parse(self, zone_text: str) -> list[ReferenceEntry]:
        blocks = [block for block in self._blocks(zone_text) if len(block) >= MIN_ENTRY_CHARS]
        return [entry for entry in self._inherited(blocks) if entry.surnames or entry.year]

    def _inherited(self, blocks: list[str]) -> list[ReferenceEntry]:
        entries, carried = [], ()
        for block in blocks:
            entry = self._entry(block)
            if _REPEAT_AUTHOR_RE.match(block) and carried and not entry.surnames:
                entry = ReferenceEntry(entry.raw, carried, entry.year)
            carried = entry.surnames or carried
            entries.append(entry)
        return entries

    def _blocks(self, zone_text: str) -> list[str]:
        blocks: list[str] = []
        for line in zone_text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if self._starts_entry(stripped) or not blocks:
                blocks.append(stripped)
            else:
                blocks[-1] = f"{blocks[-1]} {stripped}"[:MAX_ENTRY_CHARS]
        return blocks

    def _starts_entry(self, line: str) -> bool:
        return bool(_REPEAT_AUTHOR_RE.match(line) or _ENTRY_OPENING_RE.match(line))

    def _entry(self, block: str) -> ReferenceEntry:
        year = YEAR_RE.search(block)
        head = block[:year.start()] if year else block[:MAX_HEAD_CHARS]
        return ReferenceEntry(block, self._surnames(head), year.group(1) if year else None)

    @staticmethod
    def _surnames(head: str) -> tuple[str, ...]:
        return tuple(dict.fromkeys(name.lower() for name in _SURNAME_RE.findall(head)))
