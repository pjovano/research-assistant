from __future__ import annotations

from typing import NamedTuple


class Box(NamedTuple):
    left: float
    top: float
    right: float
    bottom: float

    @classmethod
    def of(cls, raw) -> Box:
        return cls(*(float(value) for value in raw))

    @classmethod
    def union(cls, boxes: list[Box]) -> Box:
        return cls(min(box.left for box in boxes), min(box.top for box in boxes),
                   max(box.right for box in boxes), max(box.bottom for box in boxes))

    @property
    def center(self) -> tuple[float, float]:
        return ((self.left + self.right) / 2, (self.top + self.bottom) / 2)

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top

    @property
    def area(self) -> float:
        return max(self.width, 0.0) * max(self.height, 0.0)

    def overlap(self, other: Box) -> float:
        width = min(self.right, other.right) - max(self.left, other.left)
        height = min(self.bottom, other.bottom) - max(self.top, other.top)
        return max(width, 0.0) * max(height, 0.0)

    def height_share_held_by(self, other: Box) -> float:
        if self.height <= 0:
            return 1.0
        return max(min(self.bottom, other.bottom) - max(self.top, other.top), 0.0) / self.height

    def contains(self, point: tuple[float, float]) -> bool:
        return self.left <= point[0] <= self.right and self.top <= point[1] <= self.bottom

    def shares_a_region_with(self, other: Box) -> bool:
        return self.contains(other.center) and other.contains(self.center)

    def shares_a_column_with(self, other: Box) -> bool:
        return self.left < other.right and other.left < self.right

    def spans_rows(self, top: float, bottom: float) -> bool:
        return top <= self.bottom and bottom >= self.top


EMPTY_BOX = Box(0.0, 0.0, 0.0, 0.0)
