from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Callable

PART_BUDGET_BYTES = 240_000
DESCRIPTIONS_KEY = "descriptions"
ROUTING_KEY = "routing_placements"
ITEM_SEPARATOR_BYTES = 2
KEY_SEPARATOR_BYTES = 2


def json_bytes(value) -> int:
    return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))


class NamedWorks:
    @staticmethod
    def none(_entry: dict) -> list[str]:
        return []

    @staticmethod
    def listed(entry: dict) -> list[str]:
        return list(entry.get("works") or [])

    @staticmethod
    def judged(entry: dict) -> list[str]:
        return [entry["work"]]

    @staticmethod
    def of_the_parts(entry: dict) -> list[str]:
        return [work for part in entry["parts"] for work in part["works"]]

    @staticmethod
    def with_neighbours(entry: dict) -> list[str]:
        return [entry["work"], *(neighbour["work"] for neighbour in entry["neighbours"])]


@dataclass(frozen=True)
class SlicedKey:
    path: tuple[str, ...]
    works_of: Callable[[dict], list[str]]

    def entries(self, listing: dict) -> list[dict]:
        held = listing
        for name in self.path:
            held = (held or {}).get(name)
        return list(held or [])

    def works_named(self, listing: dict) -> set[str]:
        return {work for entry in self.entries(listing) for work in self.works_of(entry)}

    def clear(self, listing: dict) -> None:
        holder = self._holder(listing)
        if self.path[-1] in holder:
            holder[self.path[-1]] = []

    def append(self, listing: dict, entry: dict) -> None:
        self._holder(listing)[self.path[-1]].append(entry)

    def _holder(self, listing: dict) -> dict:
        holder = listing
        for name in self.path[:-1]:
            holder = holder.get(name) or {}
        return holder


CLUSTERS_KEY = SlicedKey(("clusters", "clusters"), NamedWorks.none)
STRAYS_KEY = SlicedKey(("stray_placements",), NamedWorks.none)
SLICED_KEYS = (
    SlicedKey(("clusters", "findings", "new"), NamedWorks.listed),
    SlicedKey(("clusters", "findings", "split"), NamedWorks.of_the_parts),
    SlicedKey(("authors",), NamedWorks.listed),
    SlicedKey(("author_maps",), NamedWorks.none),
    SlicedKey(("unlinked_subtopics",), NamedWorks.none),
    SlicedKey(("co_placed",), NamedWorks.listed),
    SlicedKey(("catalogue_gaps",), NamedWorks.none),
    SlicedKey(("fold_candidates",), NamedWorks.listed),
    SlicedKey(("nominations",), NamedWorks.listed),
    SlicedKey(("clusters", "findings", "misfit"), NamedWorks.judged),
    SlicedKey((ROUTING_KEY,), NamedWorks.with_neighbours),
)


class DescribedWorks:
    @staticmethod
    def named_in(listing: dict) -> set[str]:
        return {work for key in SLICED_KEYS for work in key.works_named(listing)}


@dataclass(frozen=True)
class PartFrame:
    blank: dict
    descriptions: dict[str, dict]
    strays: dict[str, dict]
    budget: int

    @classmethod
    def of(cls, listing: dict, budget: int) -> PartFrame:
        blank = copy.deepcopy({name: held for name, held in listing.items() if name != DESCRIPTIONS_KEY})
        for key in (CLUSTERS_KEY, STRAYS_KEY, *SLICED_KEYS):
            key.clear(blank)
        strays = {stray["work"]: stray for stray in STRAYS_KEY.entries(listing)}
        return cls({**blank, DESCRIPTIONS_KEY: {}}, listing.get(DESCRIPTIONS_KEY) or {}, strays, budget)

    def about(self, work: str) -> list[dict]:
        return [self.strays[work]] if work in self.strays else []


class ListingPart:
    def __init__(self, frame: PartFrame) -> None:
        self._frame = frame
        self.content = copy.deepcopy(frame.blank)
        self._bytes = json_bytes(frame.blank)
        self.is_empty = True

    def fits(self, key: SlicedKey, entries: list[dict]) -> bool:
        return self._bytes + self._cost(key, entries) <= self._frame.budget

    def add(self, key: SlicedKey, entry: dict) -> None:
        self._bytes += self._cost(key, [entry])
        for work in self._undescribed(key, [entry]):
            self._describe(work)
        key.append(self.content, entry)
        self.is_empty = False

    def _describe(self, work: str) -> None:
        self.content[DESCRIPTIONS_KEY][work] = self._frame.descriptions[work]
        for stray in self._frame.about(work):
            STRAYS_KEY.append(self.content, stray)

    def _cost(self, key: SlicedKey, entries: list[dict]) -> int:
        listed = sum(json_bytes(entry) + ITEM_SEPARATOR_BYTES for entry in entries)
        return listed + sum(self._description_bytes(work) for work in self._undescribed(key, entries))

    def _undescribed(self, key: SlicedKey, entries: list[dict]) -> list[str]:
        named = {work for entry in entries for work in key.works_of(entry)}
        described = self.content[DESCRIPTIONS_KEY]
        return sorted(work for work in named if work in self._frame.descriptions and work not in described)

    def _description_bytes(self, work: str) -> int:
        description = self._frame.descriptions[work]
        strays = sum(json_bytes(stray) + ITEM_SEPARATOR_BYTES for stray in self._frame.about(work))
        return json_bytes(work) + KEY_SEPARATOR_BYTES + json_bytes(description) + ITEM_SEPARATOR_BYTES + strays


class PartPacking:
    def __init__(self, frame: PartFrame) -> None:
        self._frame = frame
        self._parts = [ListingPart(frame)]

    def take(self, key: SlicedKey, entries: list[dict]) -> None:
        if self._fits_only_a_part_of_its_own(key, entries):
            self._open()
        for entry in entries:
            self._take_one(key, entry)

    def parts(self) -> list[dict]:
        held = [part.content for part in self._parts if not part.is_empty]
        return held or [self._parts[0].content]

    def _fits_only_a_part_of_its_own(self, key: SlicedKey, entries: list[dict]) -> bool:
        return not self._current.fits(key, entries) and ListingPart(self._frame).fits(key, entries)

    def _take_one(self, key: SlicedKey, entry: dict) -> None:
        if not (self._current.fits(key, [entry]) or self._current.is_empty):
            self._open()
        self._current.add(key, entry)

    def _open(self) -> None:
        if not self._current.is_empty:
            self._parts.append(ListingPart(self._frame))

    @property
    def _current(self) -> ListingPart:
        return self._parts[-1]


class ListingParts:
    def __init__(self, listing: dict, budget: int = PART_BUDGET_BYTES) -> None:
        self._listing = listing
        self._budget = budget

    def cut(self) -> list[dict]:
        if json_bytes(self._listing) <= self._budget:
            return [self._listing]
        packing = PartPacking(PartFrame.of(self._listing, self._budget))
        for key in SLICED_KEYS:
            packing.take(key, key.entries(self._listing))
        return packing.parts()
