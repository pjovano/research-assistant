from __future__ import annotations

import json
import sys
from pathlib import Path

from .outline import Outline, OutlineError, ProposedOutline

STDIN_SOURCE = "-"


class EntrySource:
    def __init__(self, source: str) -> None:
        self._source = source

    def payload(self) -> object:
        return json.loads(self._text())

    def _text(self) -> str:
        if self._source == STDIN_SOURCE:
            return sys.stdin.read()
        return Path(self._source).read_text(encoding="utf-8")


class EntrySources:
    def __init__(self, sources: list[str]) -> None:
        self._sources = sources

    def payload(self) -> object:
        payloads = [EntrySource(source).payload() for source in self._sources]
        if len(payloads) == 1:
            return payloads[0]
        if not all(isinstance(payload, list) for payload in payloads):
            raise OutlineError("every --entries file joined to another must hold a JSON list of entries")
        return [entry for payload in payloads for entry in payload]


class OutlineProposal:
    def __init__(self, sources: list[str], page_count: int) -> None:
        self._sources = sources
        self._page_count = page_count

    def outline(self) -> Outline:
        return self._draft().build()

    def outline_allowing_empty(self) -> Outline:
        return self._draft().build_allowing_empty()

    def _draft(self) -> ProposedOutline:
        return ProposedOutline(EntrySources(self._sources).payload(), self._page_count)
