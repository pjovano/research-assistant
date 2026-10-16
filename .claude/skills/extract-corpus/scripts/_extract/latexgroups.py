from __future__ import annotations

_CLOSINGS = {"{": "}", "[": "]"}


def closing_of(latex: str, start: int) -> int | None:
    opening, depth = latex[start], 0
    closing = _CLOSINGS[opening]
    for index in range(start, len(latex)):
        depth += (latex[index] == opening) - (latex[index] == closing)
        if depth == 0:
            return index
    return None
