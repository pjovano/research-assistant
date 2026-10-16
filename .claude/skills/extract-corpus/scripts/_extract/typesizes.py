from __future__ import annotations

import statistics

from _extract.layerhtml import RAISED_OFFSET_SHARE
from _extract.layerlines import RAISED_SIZE_SHARE


class TypeSize:
    def __init__(self, rows: list[list]) -> None:
        self._rows = rows

    def median(self) -> float | None:
        sizes = [char.size for row in self._rows for char in _set_on_the_line(row)]
        return statistics.median(sizes) if sizes else None


class LinePitch:
    def __init__(self, rows: list[list]) -> None:
        self._rows = rows

    def median(self) -> float | None:
        baselines = sorted(_baseline_of(row) for row in self._rows if _set_on_the_line(row))
        steps = [lower - upper for upper, lower in zip(baselines, baselines[1:])]
        return statistics.median(steps) if steps else None


def _baseline_of(row: list) -> float:
    return statistics.median(char.baseline for char in _set_on_the_line(row))


def _set_on_the_line(row: list) -> list:
    on_the_line = []
    for char in (char for char in row if _sets_type(char)):
        if not on_the_line or not _is_a_script_of(char, on_the_line[-1]):
            on_the_line.append(char)
    return on_the_line


def _sets_type(char) -> bool:
    return not (char.is_blank or char.in_margin)


def _is_a_script_of(char, base) -> bool:
    is_smaller = char.size < RAISED_SIZE_SHARE * base.size
    is_off_the_baseline = abs(char.baseline - base.baseline) > RAISED_OFFSET_SHARE * base.size
    return is_smaller and is_off_the_baseline
