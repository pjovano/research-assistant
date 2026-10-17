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
NO_OTHER_DOMAIN = (DOMAIN_MANIFEST,)
LEDGER_MANIFEST = FIXTURES_DIR / "domain-manifests" / "ledger" / MANIFEST_NAME
SETTINGS_FILE = PROJECT_ROOT / ".claude" / "settings.json"
GENERATED_BLOCKS = ("permissions", "sandbox")
DOCUMENTS_PREFIX = f"{DOCUMENTS}/"
PERMISSION_DENIALS = "deny"
SANDBOX_DENIALS = "denyRead"
FILESYSTEM = "filesystem"
READ_RULE_OPENING = "Read("
GUARDING_DOMAIN = "guarding-domain"
GUARDING_SUMMARY = "Lists as sensitive each folder a read guard of the committed settings names."
READ_ACCESS = "read"


class DomainCommand:
    def __init__(self, *arguments: str | Path) -> None:
        self._arguments = [str(argument) for argument in arguments]

    def output(self) -> object:
        completed = subprocess.run([sys.executable, str(DOMAIN_SCRIPT), *self._arguments], capture_output=True,
                                   text=True, cwd=PROJECT_ROOT, check=True)
        return json.loads(completed.stdout)


class GeneratedSettings:
    def __init__(self, neighbours: tuple[Path, ...] = NO_OTHER_DOMAIN) -> None:
        self._neighbours = neighbours

    def blocks(self) -> dict:
        return DomainCommand("settings", "--domain", DOMAIN_MANIFEST, *self._neighbours).output()


class CommittedSettings:
    @staticmethod
    def blocks() -> dict:
        settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return {block: settings[block] for block in GENERATED_BLOCKS}


class GuardingManifest:
    def __init__(self, folders: set[str]) -> None:
        self._folders = folders

    def written(self, directory: Path) -> Path:
        path = directory / GUARDING_DOMAIN / MANIFEST_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._manifest()), encoding="utf-8")
        return path

    def _manifest(self) -> dict:
        folders = [{"name": folder, "access": READ_ACCESS, "sensitive": True} for folder in sorted(self._folders)]
        return {"name": GUARDING_DOMAIN, "summary": GUARDING_SUMMARY, "folders": folders}


class RegeneratedSettings:
    def __init__(self, blocks: dict, directory: Path) -> None:
        self._blocks = blocks
        self._directory = directory

    def blocks(self) -> dict:
        manifest = GuardingManifest(ReadGuards(self._blocks).folders()).written(self._directory)
        return GeneratedSettings((manifest,)).blocks()


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


class ReadGuards:
    def __init__(self, blocks: dict) -> None:
        self._blocks = blocks

    def folders(self) -> set[str]:
        return self.sandbox_folders() | self.read_rule_folders()

    def sandbox_folders(self) -> set[str]:
        return DocumentsFolders(self._blocks["sandbox"][FILESYSTEM].get(SANDBOX_DENIALS, [])).names()

    def read_rule_folders(self) -> set[str]:
        rules = self._blocks["permissions"].get(PERMISSION_DENIALS, [])
        return DocumentsFolders([rule.removeprefix(READ_RULE_OPENING) for rule in rules]).names()

    def without_read_rules(self) -> dict:
        permissions = {key: value for key, value in self._blocks["permissions"].items() if key != PERMISSION_DENIALS}
        return {**self._blocks, "permissions": permissions}
