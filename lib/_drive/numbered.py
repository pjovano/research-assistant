from __future__ import annotations

from pathlib import Path

NUMBER_SLOT = "{n}"
COUNT_FIELD = "count"
FIRST_NUMBER = 1


class NumberedFiles:
    def __init__(self, count: int, names: dict[str, str]) -> None:
        self._count = count
        self._names = names

    def as_field(self) -> dict:
        return {COUNT_FIELD: self._count, **self._names}

    @staticmethod
    def name(template: str, number: int) -> str:
        return template.replace(NUMBER_SLOT, str(number))

    @classmethod
    def expanded(cls, directory: str | Path, field: dict) -> list[dict[str, str]]:
        names = {key: template for key, template in field.items() if key != COUNT_FIELD}
        numbers = range(FIRST_NUMBER, FIRST_NUMBER + field[COUNT_FIELD])
        return [{key: str(Path(directory) / cls.name(template, number)) for key, template in names.items()}
                for number in numbers]
