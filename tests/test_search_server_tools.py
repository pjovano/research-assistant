from __future__ import annotations

import importlib.util
import json
import sys
import unittest

from _support import PROJECT_ROOT, SKILLS_DIR, LiveTree

LiveTree.activate()

SERVER_PATH = SKILLS_DIR / "search" / "server.py"
SETTINGS_PATH = PROJECT_ROOT / ".claude" / "settings.json"
TOOL_PERMISSION_PREFIX = "mcp__vault-rag__"


class SearchServerModule:
    @staticmethod
    def loaded():
        spec = importlib.util.spec_from_file_location("entry_search_server_tools", SERVER_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module


class AllowedTools:
    @staticmethod
    def names() -> set[str]:
        allowed = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))["permissions"]["allow"]
        return {entry.removeprefix(TOOL_PERMISSION_PREFIX) for entry in allowed
                if entry.startswith(TOOL_PERMISSION_PREFIX)}


class TestTheServerRegistersEveryToolTheSettingsAllow(unittest.TestCase):
    def setUp(self) -> None:
        self.server = SearchServerModule.loaded()

    def test_the_registered_tools_are_exactly_the_tools_the_settings_allow(self) -> None:
        self.assertEqual(AllowedTools.names(), set(self.server.TOOL_DESCRIPTIONS))

    def test_every_registered_tool_is_served_by_the_handler_of_its_name(self) -> None:
        unserved = [name for name in self.server.TOOL_DESCRIPTIONS
                    if not callable(getattr(self.server.VaultRagServer, name, None))]
        self.assertEqual([], unserved)

    def test_every_registered_tool_carries_a_description(self) -> None:
        undescribed = [name for name, description in self.server.TOOL_DESCRIPTIONS.items() if not description.strip()]
        self.assertEqual([], undescribed)


if __name__ == "__main__":
    unittest.main()
