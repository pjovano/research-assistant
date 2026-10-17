from __future__ import annotations

import json
import subprocess
import sys

from _support import PROJECT_ROOT

DOMAIN_SCRIPT = PROJECT_ROOT / "vendor" / "agent-core" / "domain.py"
DOMAIN_MANIFEST = PROJECT_ROOT / "domain.json"
SETTINGS_FILE = PROJECT_ROOT / ".claude" / "settings.json"
GENERATED_BLOCKS = ("permissions", "sandbox")
DOCUMENTS_PREFIX = "~/Documents/"
PERMISSION_DENIALS = "deny"
SANDBOX_DENIALS = "denyRead"
FILESYSTEM = "filesystem"
READ_RULE_OPENING = "Read("


class GeneratedSettings:
    @staticmethod
    def blocks() -> dict:
        completed = subprocess.run([sys.executable, str(DOMAIN_SCRIPT), "settings", "--domain", str(DOMAIN_MANIFEST),
                                    str(DOMAIN_MANIFEST)], capture_output=True, text=True, cwd=PROJECT_ROOT,
                                   check=True)
        return json.loads(completed.stdout)


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


class ReadGuards:
    def __init__(self, blocks: dict) -> None:
        self._blocks = blocks

    def removed(self) -> dict:
        permissions = {key: value for key, value in self._blocks["permissions"].items() if key != PERMISSION_DENIALS}
        sandbox = dict(self._blocks["sandbox"])
        sandbox[FILESYSTEM] = {key: value for key, value in sandbox[FILESYSTEM].items() if key != SANDBOX_DENIALS}
        return {"permissions": permissions, "sandbox": sandbox}

    def sandbox_folders(self) -> set[str]:
        return DocumentsFolders(self._blocks["sandbox"][FILESYSTEM].get(SANDBOX_DENIALS, [])).names()

    def read_rule_folders(self) -> set[str]:
        rules = self._blocks["permissions"].get(PERMISSION_DENIALS, [])
        return DocumentsFolders([rule.removeprefix(READ_RULE_OPENING) for rule in rules]).names()
