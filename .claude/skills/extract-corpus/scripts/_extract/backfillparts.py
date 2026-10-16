from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from _drive.numbered import NUMBER_SLOT, NumberedFiles
from _drive.work import WorkDirectory

MAX_SCOPE_PAGES_PER_DISPATCH = 12
MAX_CLEANUP_PAGES_PER_DISPATCH = 25
PAGES_KEY = "pages"
FILE_PAGE_KEY = "file_page"
LOOK_AHEAD_KEY = "look_ahead"
PART_KEY = "part"
REPAIR_TAG = "repair"


def balanced_runs(items: list, cap: int) -> list[list]:
    if not items:
        return []
    count = math.ceil(len(items) / cap)
    size, larger = divmod(len(items), count)
    bounds = [index * size + min(index, larger) for index in range(count + 1)]
    return [items[bounds[index]:bounds[index + 1]] for index in range(count)]


def whole_context(shared: dict, _pages: list[dict]) -> dict:
    return shared


@dataclass(frozen=True)
class PartNames:
    listing: str
    verdicts: str
    judged_key: str
    findings_key: str
    cap: int
    looks_ahead: bool
    context_of: Callable[[dict, list[dict]], dict]


SCOPE_PARTS = PartNames("scope", "scope-verdicts", "pages_judged", "spans", MAX_SCOPE_PAGES_PER_DISPATCH, True,
                        whole_context)
CLEANUP_PARTS = PartNames("cleanup", "corrections", "pages_read", "corrections", MAX_CLEANUP_PAGES_PER_DISPATCH,
                          False, whole_context)


@dataclass(frozen=True)
class MergedVerdicts:
    judged: frozenset[int]
    findings: list

    def omitted(self, listed: list[int]) -> list[int]:
        return [page for page in listed if page not in self.judged]


class PartedListing:
    def __init__(self, listing: dict, names: PartNames) -> None:
        self._listing = listing
        self._names = names
        self._pages = listing[PAGES_KEY]

    @property
    def listed(self) -> list[int]:
        return [page[FILE_PAGE_KEY] for page in self._pages]

    def parts(self, only: list[int] | None = None) -> list[dict]:
        wanted = [page for page in self._pages if only is None or page[FILE_PAGE_KEY] in only]
        runs = balanced_runs(wanted, self._names.cap)
        return [self._part(run, number + 1, len(runs)) for number, run in enumerate(runs)]

    def _part(self, run: list[dict], number: int, count: int) -> dict:
        shared = {key: value for key, value in self._listing.items() if key != PAGES_KEY}
        part = {**self._names.context_of(shared, run), PART_KEY: {"number": number, "of": count}, PAGES_KEY: run}
        if self._names.looks_ahead:
            part[LOOK_AHEAD_KEY] = self._page_after(run[-1][FILE_PAGE_KEY])
        return part

    def _page_after(self, file_page: int) -> dict | None:
        return next((page for page in self._pages if page[FILE_PAGE_KEY] > file_page), None)


class PartedDispatch:
    def __init__(self, work: WorkDirectory, names: PartNames) -> None:
        self._work = work
        self._names = names

    def write(self, listing_text: str) -> None:
        self._work.write_text(f"{self._names.listing}.json", listing_text)
        self._work.discard(f"{self._names.listing}-{PART_KEY}-*.json")
        for part in self._listing().parts():
            self._work.save(self._part_name(part[PART_KEY]["number"]), part)

    def dispatch(self, round_number: int) -> dict:
        self._work.discard(f"{self._names.verdicts}-{round_number}-*.json")
        self._work.discard(f"{self._names.listing}-{REPAIR_TAG}-{round_number}-*.json")
        return self._dispatched(len(self._listing().parts()), self._part_name(NUMBER_SLOT), str(round_number))

    def repair(self, round_number: int, pages: list[int]) -> dict:
        attempt = len(self._work.matching(f"{self._names.listing}-{REPAIR_TAG}-{round_number}-*-1.json")) + 1
        listing = f"{self._names.listing}-{REPAIR_TAG}-{round_number}-{attempt}-{NUMBER_SLOT}.json"
        parts = self._listing().parts(only=pages)
        for part in parts:
            self._work.save(NumberedFiles.name(listing, part[PART_KEY]["number"]), part)
        return self._dispatched(len(parts), listing, f"{round_number}-{REPAIR_TAG}-{attempt}")

    def listed(self) -> list[int]:
        return self._listing().listed

    def merged(self, round_number: int) -> MergedVerdicts:
        judged: set[int] = set()
        findings: list = []
        for path in self._work.matching(f"{self._names.verdicts}-{round_number}-*.json"):
            verdicts = self._readable(path)
            judged.update(page for page in verdicts.get(self._names.judged_key) or [] if isinstance(page, int))
            findings += verdicts.get(self._names.findings_key) or []
        return MergedVerdicts(frozenset(judged), findings)

    @staticmethod
    def _readable(path: Path) -> dict:
        try:
            verdicts = json.loads(path.read_text())
        except (OSError, ValueError):
            return {}
        return verdicts if isinstance(verdicts, dict) else {}

    def _listing(self) -> PartedListing:
        return PartedListing(self._work.load(f"{self._names.listing}.json"), self._names)

    def _part_name(self, number: int | str) -> str:
        return f"{self._names.listing}-{PART_KEY}-{number}.json"

    def _dispatched(self, count: int, listing: str, verdicts_tag: str) -> dict:
        verdicts = f"{self._names.verdicts}-{verdicts_tag}-{NUMBER_SLOT}.json"
        return NumberedFiles(count, {"listing": listing, "verdicts": verdicts}).as_field()
