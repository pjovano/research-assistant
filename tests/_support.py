from __future__ import annotations

import json
import sys
from pathlib import Path

from _engine_refusal import EngineServerRefusal

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"
FIXTURES_DIR = TESTS_DIR / "fixtures"
GOLDENS_DIR = FIXTURES_DIR / "goldens"
VENDORED_CORE_LIB = PROJECT_ROOT / "vendor" / "agent-core" / "lib"


class ModuleSearchPath:
    def __init__(self, lib_dir: Path, skills_dir: Path, core_lib_dir: Path = VENDORED_CORE_LIB) -> None:
        self._lib_dir = lib_dir
        self._skills_dir = skills_dir
        self._core_lib_dir = core_lib_dir

    def directories(self) -> list[Path]:
        return [self._core_lib_dir, self._lib_dir] + sorted(self._skills_dir.glob("*/scripts"))

    def activate(self) -> None:
        for directory in self.directories():
            self._prepend(directory)

    def _prepend(self, directory: Path) -> None:
        entry = str(directory)
        if entry not in sys.path:
            sys.path.insert(0, entry)


class LiveTree:
    @staticmethod
    def activate() -> None:
        ModuleSearchPath(PROJECT_ROOT / "lib", SKILLS_DIR).activate()
        EngineServerRefusal.install()


class JsonDocument:
    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def exists(self) -> bool:
        return self._path.exists()

    def load(self) -> object:
        return json.loads(self._path.read_text(encoding="utf-8"))

    def rendered(self, payload: object) -> str:
        return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"

    def matches(self, payload: object) -> bool:
        return self.exists() and self._path.read_text(encoding="utf-8") == self.rendered(payload)

    def save(self, payload: object) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(self.rendered(payload), encoding="utf-8", newline="\n")


class Golden(JsonDocument):
    def __init__(self, name: str) -> None:
        super().__init__(GOLDENS_DIR / f"{name}.json")
