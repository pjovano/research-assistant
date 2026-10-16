from __future__ import annotations

import statistics

SAME_BASELINE_SHARE = 0.4


class LineMeasures:
    def __init__(self, lines: list[list]) -> None:
        self._bounds = {id(line): bounds_of(line) for line in lines}
        self._baselines = {id(line): baseline_of(line) for line in lines}
        self._sizes = {id(line): size_of(line) for line in lines}
        self._inked_counts = {id(line): len(inked(line)) for line in lines}

    def bounds(self, line: list) -> tuple[float, float, float, float]:
        return self._bounds[id(line)]

    def baseline(self, line: list) -> float:
        return self._baselines[id(line)]

    def size(self, line: list) -> float:
        return self._sizes[id(line)]

    def inked_count(self, line: list) -> int:
        return self._inked_counts[id(line)]

    def share_baseline(self, first: list, second: list) -> bool:
        pair = (first, second)
        return baselines_agree([self.baseline(line) for line in pair], [self.size(line) for line in pair])

    def rows(self, lines: list[list]) -> list[list[list]]:
        rows: list[list[list]] = []
        for line in sorted(lines, key=self.baseline):
            if rows and self.share_baseline(rows[-1][-1], line):
                rows[-1].append(line)
            else:
                rows.append([line])
        return rows


def share_a_baseline(lines: list[list] | tuple[list, ...]) -> bool:
    return baselines_agree([baseline_of(line) for line in lines], [size_of(line) for line in lines])


def baselines_agree(baselines: list[float], sizes: list[float]) -> bool:
    return max(baselines) - min(baselines) <= SAME_BASELINE_SHARE * max(sizes)


def inked(line: list) -> list:
    return [char for char in line if not char.is_blank] or line


def baseline_of(line: list) -> float:
    return statistics.median([char.baseline for char in inked(line)])


def size_of(line: list) -> float:
    return statistics.median([char.size for char in inked(line)])


def bounds_of(line: list) -> tuple[float, float, float, float]:
    boxes = [char.bbox for char in inked(line)]
    return (min(box[0] for box in boxes), min(box[1] for box in boxes),
            max(box[2] for box in boxes), max(box[3] for box in boxes))
