from __future__ import annotations


def spread(items: list, limit: int) -> list:
    return [items[position] for position in spread_positions(len(items), limit)]


def spread_positions(count: int, limit: int) -> list[int]:
    last = count - 1
    if last < 0:
        return []
    steps = max(limit - 1, 1)
    return sorted({round(step * last / steps) for step in range(limit)})
