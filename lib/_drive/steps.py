from __future__ import annotations

import hashlib
import json
import subprocess
import unicodedata
from collections.abc import Callable
from pathlib import Path

import vault

from _drive.work import STATE_ASIDE, WorkDirectory, WorkStops

EXIT_OK = 0
QUOTATION_MARK_NAME = "QUOTATION MARK"
CONTROL_CATEGORY = "Cc"
BACKSLASH = "\\"
APOSTROPHE = "'"
SLASH = "/"
SPACE = " "
NEWLINE = "\n"
LINE_LIMIT = 8000
RELAYED_LINE_LIMIT = 700
FORWARDED_FIELDS = frozenset({"question", "questions", "notes", "classes", "created", "moved", "linked", "unlinked",
                              "added", "folded", "checked_off"})
SPILLED_TEXT_OPENING = 200
SPILLED_NAME = "spilled"
DIGEST_LENGTH = 12


class StepGuard:
    def __init__(self, command: str) -> None:
        self._command = command

    def outcome(self, action: Callable[[], dict]) -> dict:
        try:
            return action()
        except WorkStops as stop:
            return stop.fields
        except subprocess.TimeoutExpired:
            return {"state": STATE_ASIDE, "question": f"{self._command} timed out"}
        except Exception as error:
            return {"state": STATE_ASIDE, "question": f"{self._command} error: {type(error).__name__}: {error}"}

    def on_work(self, find_work: Callable[[], WorkDirectory], step: Callable[[WorkDirectory], dict]) -> dict:
        return self.outcome(lambda: self._step_on(find_work(), step))

    def _step_on(self, work: WorkDirectory, step: Callable[[WorkDirectory], dict]) -> dict:
        return work.outcome(self.outcome(lambda: step(work)))


class RelaySafeText:
    @classmethod
    def of(cls, value):
        if isinstance(value, str):
            return "".join(cls._character(character) for character in value)
        if isinstance(value, dict):
            return {key: cls.of(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls.of(item) for item in value]
        return value

    @staticmethod
    def _character(character: str) -> str:
        if QUOTATION_MARK_NAME in unicodedata.name(character, ""):
            return APOSTROPHE
        if character == BACKSLASH:
            return SLASH
        if unicodedata.category(character) == CONTROL_CATEGORY:
            return SPACE
        return character


class BoundedOutcome:
    def __init__(self, outcome: dict, directory: Path) -> None:
        self._outcome = outcome
        self._directory = directory

    def of(self) -> dict:
        bounded = self._spilled_until(dict(self._outcome), self._is_forwarded, RELAYED_LINE_LIMIT)
        return self._spilled_until(bounded, self._is_list, LINE_LIMIT)

    def _spilled_until(self, outcome: dict, is_spillable: Callable[[str, object], bool], limit: int) -> dict:
        for name in self._largest_first(outcome, is_spillable):
            if self._fits(outcome, limit):
                break
            outcome[name] = self._spilled(name, outcome[name])
        return outcome

    @staticmethod
    def _largest_first(outcome: dict, is_spillable: Callable[[str, object], bool]) -> list[str]:
        names = [name for name, value in outcome.items() if is_spillable(name, value)]
        return sorted(names, key=lambda name: len(json.dumps(outcome[name], ensure_ascii=False)), reverse=True)

    @staticmethod
    def _is_forwarded(name: str, value) -> bool:
        return name in FORWARDED_FIELDS and isinstance(value, (list, str))

    @staticmethod
    def _is_list(_name: str, value) -> bool:
        return isinstance(value, list)

    @staticmethod
    def _fits(outcome: dict, limit: int) -> bool:
        return len(json.dumps(outcome, ensure_ascii=False)) <= limit

    def _spilled(self, name: str, value):
        if isinstance(value, str):
            return f"{value[:SPILLED_TEXT_OPENING]} […] whole in {self._written(name, value)}"
        lines = [item if isinstance(item, str) else json.dumps(item, ensure_ascii=False) for item in value]
        return [f"{len(value)} {name}, one to a line, in {self._written(name, NEWLINE.join(lines))}"]

    def _written(self, name: str, text: str) -> Path:
        content = text + NEWLINE
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:DIGEST_LENGTH]
        path = self._directory / f"{name}-{digest}.txt"
        self._directory.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path


class JsonLine:
    @staticmethod
    def emit(outcome: dict) -> int:
        bounded = BoundedOutcome(RelaySafeText.of(outcome), vault.SCRATCH_DIR / SPILLED_NAME).of()
        print(json.dumps(bounded, ensure_ascii=False))
        return EXIT_OK
