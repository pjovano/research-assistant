from __future__ import annotations

import json
import shutil
from pathlib import Path

from .answermerge import MergedAnswers

LISTING_NAME = "listing.json"
ANSWERS_NAME = "answers.json"


class PartsDirectory:
    def __init__(self, root: Path) -> None:
        self._root = root

    def write(self, parts: list[dict]) -> None:
        for stale in self._numbered():
            shutil.rmtree(stale)
        for number, part in enumerate(parts, 1):
            listing = self._root / str(number) / LISTING_NAME
            listing.parent.mkdir(parents=True)
            listing.write_text(json.dumps(part, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def numbers(self) -> list[int]:
        return [int(directory.name) for directory in self._numbered() if (directory / LISTING_NAME).exists()]

    def answers(self) -> dict[int, dict]:
        read = {number: self._answers_of(number) for number in self.numbers()}
        return {number: answers for number, answers in read.items() if answers is not None}

    def _numbered(self) -> list[Path]:
        if not self._root.is_dir():
            return []
        numbered = [directory for directory in self._root.iterdir() if directory.is_dir() and directory.name.isdigit()]
        return sorted(numbered, key=lambda directory: int(directory.name))

    def _answers_of(self, number: int) -> dict | None:
        try:
            answers = json.loads((self._root / str(number) / ANSWERS_NAME).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return answers if isinstance(answers, dict) else None


class PartAnswers:
    def __init__(self, directory: PartsDirectory) -> None:
        self._numbers = directory.numbers()
        self._answers = directory.answers()

    def merged(self) -> dict:
        merged = MergedAnswers(list(self._answers.values())).merged()
        return {**merged, "questions": merged["questions"] + self._unanswered_question()}

    def report(self) -> dict:
        return {"parts": len(self._numbers), "answered": len(self._answers)}

    def _unanswered_question(self) -> list[str]:
        unanswered = [str(number) for number in self._numbers if number not in self._answers]
        if not unanswered:
            return []
        return [f"the bibliography shaper wrote no answers file for part {', '.join(unanswered)} of "
                f"{len(self._numbers)} of the listing; the next reshaping judges its entries again"]
