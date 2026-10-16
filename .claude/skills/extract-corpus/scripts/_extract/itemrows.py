from __future__ import annotations

from _extract.notenumbers import LAYER_LINE_OPENING_RE


class ListItemRows:
    def __init__(self, row_texts: list[str]) -> None:
        self._row_texts = row_texts

    def items(self) -> list[str]:
        own_number = _number_of(self._row_texts[0]) if self._row_texts else None
        if own_number is None:
            return [" ".join(self._row_texts)]
        items: list[list[str]] = []
        for row_text in self._row_texts:
            if items and _number_of(row_text) != own_number + len(items):
                items[-1].append(row_text)
            else:
                items.append([row_text])
        return [" ".join(rows) for rows in items]


def _number_of(row_text: str) -> int | None:
    opening = LAYER_LINE_OPENING_RE.match(row_text)
    return int(opening.group(1)) if opening else None
