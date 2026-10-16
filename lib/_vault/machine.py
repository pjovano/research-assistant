from __future__ import annotations

import json
from pathlib import Path

MACHINE_CONFIG_PATH = Path.home() / ".research-vault" / "machine.json"
_ENCODING = "utf-8"


class MachineConfig:
    def __init__(self, path: Path) -> None:
        self._path = path

    def loaded(self) -> dict:
        try:
            text = self._path.read_text(encoding=_ENCODING)
        except OSError:
            return {}
        return self._parsed(text)

    def _parsed(self, text: str) -> dict:
        try:
            return json.loads(text) or {}
        except ValueError as error:
            raise SystemExit(f"{self._path} is not valid JSON: {error}") from error


def load_machine_config() -> dict:
    return MachineConfig(MACHINE_CONFIG_PATH).loaded()
