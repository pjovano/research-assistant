from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from _support import FIXTURES_DIR, PROJECT_ROOT, LiveTree

LiveTree.activate()

from agent_core._domain.manifest import DOCUMENTS, MANIFEST_NAME

DOMAIN_SCRIPT = PROJECT_ROOT / "vendor" / "agent-core" / "domain.py"
DOMAIN_MANIFEST = PROJECT_ROOT / MANIFEST_NAME
LEDGER_MANIFEST = FIXTURES_DIR / "domain-manifests" / "ledger" / MANIFEST_NAME
SETTINGS_FILE = PROJECT_ROOT / ".claude" / "settings.json"
LOCAL_SETTINGS = ".claude/settings.local.json"
GENERATED_BLOCKS = ("permissions", "sandbox")
DOCUMENTS_PREFIX = f"{DOCUMENTS}/"


class DomainCommand:
    def __init__(self, *arguments: str | Path) -> None:
        self._arguments = [str(argument) for argument in arguments]

    def output(self) -> object:
        completed = subprocess.run([sys.executable, str(DOMAIN_SCRIPT), *self._arguments], capture_output=True,
                                   text=True, cwd=PROJECT_ROOT, check=True)
        return json.loads(completed.stdout)


class GeneratedSettings:
    @staticmethod
    def blocks() -> dict:
        return DomainCommand("settings", "--domain", DOMAIN_MANIFEST).output()


class GeneratedGuards:
    def __init__(self, *neighbours: Path) -> None:
        self._neighbours = neighbours

    def blocks(self) -> dict:
        return DomainCommand("guards", "--domain", DOMAIN_MANIFEST, *self._neighbours).output()

    def denied_reads(self) -> list[str]:
        return self.blocks()["sandbox"]["filesystem"]["denyRead"]

    def denied_rules(self) -> list[str]:
        return self.blocks()["permissions"]["deny"]


class CommittedSettings:
    @staticmethod
    def blocks() -> dict:
        settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return {block: settings[block] for block in GENERATED_BLOCKS}


class Unordered:
    def __init__(self, value: object) -> None:
        self._value = value

    def canonical(self) -> object:
        if isinstance(self._value, dict):
            return {key: Unordered(child).canonical() for key, child in self._value.items()}
        if isinstance(self._value, list):
            return sorted((Unordered(child).canonical() for child in self._value), key=json.dumps)
        return self._value


class DocumentsFolders:
    def __init__(self, paths: list[str]) -> None:
        self._paths = paths

    def names(self) -> set[str]:
        return {path.removeprefix(DOCUMENTS_PREFIX).split("/")[0] for path in self._paths
                if path.startswith(DOCUMENTS_PREFIX)}
