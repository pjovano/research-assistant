import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import harness_hooks


def hook_commands() -> list[str]:
    settings = json.loads((harness_hooks.PROJECT_ROOT / ".claude" / "settings.json").read_text())
    matchers = [matcher for event in settings["hooks"].values() for matcher in event]
    return [hook["command"] for matcher in matchers for hook in matcher["hooks"]
            if "harness_hooks.py" in hook["command"]]


HOOK_SCRIPT = Path("lib/harness_hooks.py")


class HookShell:
    def __init__(self, home: str, project_root: Path) -> None:
        self._environment = {**os.environ, "HOME": home, "CLAUDE_PROJECT_DIR": str(project_root)}

    def run(self, command: str, payload: str) -> subprocess.CompletedProcess:
        return subprocess.run(["sh", "-c", command], input=payload, capture_output=True, text=True,
                              env=self._environment)


class TestHookCommands(unittest.TestCase):
    def setUp(self):
        self.home = self.enterContext(tempfile.TemporaryDirectory())

    def _install_interpreter(self) -> None:
        environment = Path(self.home) / harness_hooks.INTERPRETER.parent.parent.relative_to(Path.home())
        environment.parent.mkdir(parents=True)
        environment.symlink_to(sys.prefix, target_is_directory=True)

    def test_every_subcommand_has_a_hook_command(self):
        commands = hook_commands()
        for subcommand in ("guard-bash", "guard-write", "checks-after-edit", "ensure-health-watcher"):
            self.assertTrue(any(subcommand in command for command in commands), subcommand)

    def test_a_missing_interpreter_blocks_from_the_shell(self):
        shell = HookShell(self.home, harness_hooks.PROJECT_ROOT)
        for command in hook_commands():
            with self.subTest(command=command):
                result = shell.run(command, payload="{}")
                self.assertEqual(result.returncode, harness_hooks.BLOCKING_EXIT_CODE, result.stderr)

    def test_a_block_the_hook_issues_itself_keeps_its_report(self):
        self._install_interpreter()
        shell = HookShell(self.home, harness_hooks.PROJECT_ROOT)
        for command in hook_commands():
            with self.subTest(command=command):
                result = shell.run(command, payload="not json")
                self.assertEqual(result.returncode, harness_hooks.BLOCKING_EXIT_CODE, result.stderr)
                self.assertIn("the hook failed", result.stderr)

    def test_a_clean_hook_run_exits_zero_from_the_shell(self):
        self._install_interpreter()
        shell = HookShell(self.home, harness_hooks.PROJECT_ROOT)
        for command in hook_commands():
            with self.subTest(command=command):
                result = shell.run(command, payload="{}")
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_write_on_a_machine_without_a_vault_passes_unguarded(self):
        self._install_interpreter()
        shell = HookShell(self.home, harness_hooks.PROJECT_ROOT)
        command = next(command for command in hook_commands() if "guard-write" in command)
        payload = json.dumps({"tool_input": {"file_path": str(Path(self.home) / "notes.md")}})
        result = shell.run(command, payload=payload)
        self.assertEqual((0, ""), (result.returncode, result.stdout), result.stderr)

    def test_a_hook_module_that_fails_at_import_still_blocks(self):
        self._install_interpreter()
        shell = HookShell(self.home, self._project_whose_hook_module_is_broken())
        for command in hook_commands():
            with self.subTest(command=command):
                result = shell.run(command, payload="{}")
                self.assertEqual(result.returncode, harness_hooks.BLOCKING_EXIT_CODE, result.stderr)
                self.assertIn("broken by an edit", result.stderr)

    def _project_whose_hook_module_is_broken(self) -> Path:
        project = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (project / HOOK_SCRIPT).parent.mkdir()
        (project / HOOK_SCRIPT).write_text("raise ImportError('broken by an edit')\n")
        return project


class TestProjectRoot(unittest.TestCase):
    def test_the_project_root_is_the_directory_holding_lib(self):
        self.assertTrue((harness_hooks.PROJECT_ROOT / HOOK_SCRIPT).is_file())


if __name__ == "__main__":
    unittest.main()
