from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import requests

import vault as vault_lib

from notation import inside_notation
from page_marker import PageMarker

if TYPE_CHECKING:
    from tiktoken import Encoding

CACHE_DIRECTORY_VARIABLE = "TIKTOKEN_CACHE_DIR"
CACHE_DIRECTORY_NAME = "tiktoken"
ENCODING_NAME = "cl100k_base"
PARAGRAPH_SEPARATOR = "\n\n"
SENTENCE_SEPARATOR = " "

_SENTENCE_BOUNDARY_RE = re.compile(r"(?:(?<=[.!?…])|(?<=[.!?…][\"”’)\]]))\s+")


class TokenizerUnavailable(RuntimeError):
    pass


class _TiktokenCache:
    def locate(self) -> None:
        os.environ.setdefault(CACHE_DIRECTORY_VARIABLE, str(self._directory()))

    @property
    def directory(self) -> str:
        return os.environ[CACHE_DIRECTORY_VARIABLE]

    @staticmethod
    def _directory() -> Path:
        return vault_lib.MACHINE_CONFIG_PATH.parent / CACHE_DIRECTORY_NAME


class TokenBudget:
    def __init__(self) -> None:
        self._encoding: Encoding | None = None

    def count(self, text: str) -> int:
        return len(self._loaded_encoding().encode(text))

    def _loaded_encoding(self) -> Encoding:
        if self._encoding is None:
            self._encoding = self._fetched_encoding(_TiktokenCache())
        return self._encoding

    @staticmethod
    def _fetched_encoding(cache: _TiktokenCache) -> Encoding:
        cache.locate()
        import tiktoken
        try:
            return tiktoken.get_encoding(ENCODING_NAME)
        except (requests.RequestException, OSError) as error:
            raise TokenizerUnavailable(
                f"the tokenizer encoding {ENCODING_NAME} is not in its cache {cache.directory} and could not be "
                f"fetched ({error}); fetch it once on a machine with network access, with {CACHE_DIRECTORY_VARIABLE} "
                "set to that directory, and every later run reads it from the cache") from error


@dataclass(frozen=True)
class Unit:
    text: str
    separator: str
    atomic: bool
    first_page: PageMarker
    last_page: PageMarker


@dataclass(frozen=True)
class Run:
    units: tuple[Unit, ...]

    @property
    def text(self) -> str:
        first, *rest = self.units
        return first.text + "".join(unit.separator + unit.text for unit in rest)

    @property
    def first_page(self) -> PageMarker:
        return self.units[0].first_page

    @property
    def last_page(self) -> PageMarker:
        return self.units[-1].last_page


class _UnitCost:
    def __init__(self, budget: TokenBudget) -> None:
        self._budget = budget
        self._counted: dict[str, int] = {}

    def tokens_of(self, text: str) -> int:
        if text not in self._counted:
            self._counted[text] = self._budget.count(text)
        return self._counted[text]


class _RunTally:
    def __init__(self, budget: TokenBudget, limit: int) -> None:
        self._budget = budget
        self._limit = limit
        self._cost = _UnitCost(budget)
        self._units: list[Unit] = []
        self._tokens = 0

    def started(self) -> bool:
        return bool(self._units)

    def overflows_with(self, unit: Unit) -> bool:
        if not self.started() or self._fits_by_tally(unit):
            return False
        return self._budget.count(Run(tuple(self._units + [unit])).text) > self._limit

    def _fits_by_tally(self, unit: Unit) -> bool:
        return self._tokens + self._addition(unit) <= self._limit

    def add(self, unit: Unit) -> None:
        self._tokens += self._addition(unit)
        self._units.append(unit)

    def taken(self) -> Run:
        run = Run(tuple(self._units))
        self._units = []
        self._tokens = 0
        return run

    def _addition(self, unit: Unit) -> int:
        separator = self._cost.tokens_of(unit.separator) if self.started() else 0
        return self._cost.tokens_of(unit.text) + separator


class UnitPacker:
    def __init__(self, budget: TokenBudget, limit: int) -> None:
        self._budget = budget
        self._limit = limit

    def runs(self, units: list[Unit]) -> list[Run]:
        tally = _RunTally(self._budget, self._limit)
        packed: list[Run] = []
        for unit in units:
            if tally.overflows_with(unit):
                packed.append(tally.taken())
            tally.add(unit)
        return packed + ([tally.taken()] if tally.started() else [])

    def fits(self, unit: Unit) -> bool:
        return self._budget.count(unit.text) <= self._limit


class SentenceSplitter:
    def sentences(self, text: str) -> list[str]:
        cuts = [cut for cut in _SENTENCE_BOUNDARY_RE.finditer(text) if not inside_notation(cut.start(), text)]
        starts = [0] + [cut.end() for cut in cuts]
        ends = [cut.start() for cut in cuts] + [len(text)]
        pieces = [text[start:end].strip() for start, end in zip(starts, ends)]
        return [piece for piece in pieces if piece]
