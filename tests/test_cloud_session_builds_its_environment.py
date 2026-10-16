import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _support import PROJECT_ROOT

START_SCRIPT = Path("bin/cloud-session-start.sh")
SETUP_SCRIPT = Path("bin/cloud-setup.sh")
BUILT_MARK = Path(".research-vault/cloud-setup.done")
LOG = Path(".research-vault/cloud-setup.log")
SETUP_RAN = "setup ran"


class StubProject:
    def __init__(self, root: Path) -> None:
        self._root = root
        (root / START_SCRIPT).parent.mkdir(parents=True)
        shutil.copy(PROJECT_ROOT / START_SCRIPT, root / START_SCRIPT)

    def setup_that_succeeds(self) -> None:
        self._setup(f'echo "{SETUP_RAN}"\ntouch "$HOME/{BUILT_MARK}"\n')

    def setup_that_fails(self) -> None:
        self._setup(f'echo "{SETUP_RAN}"\necho "pypi.org did not answer"\nexit 3\n')

    def _setup(self, body: str) -> None:
        (self._root / SETUP_SCRIPT).write_text(f"set -e\n{body}")

    @property
    def start_script(self) -> Path:
        return self._root / START_SCRIPT


class SessionStart:
    def __init__(self, home: Path, project: StubProject) -> None:
        self._home = home
        self._project = project

    def run(self, remote: str | None) -> subprocess.CompletedProcess:
        environment = {key: value for key, value in os.environ.items() if key != "CLAUDE_CODE_REMOTE"}
        environment["HOME"] = str(self._home)
        if remote is not None:
            environment["CLAUDE_CODE_REMOTE"] = remote
        return subprocess.run(["bash", str(self._project.start_script)], capture_output=True, text=True,
                              env=environment)


class TestCloudSessionBuildsItsEnvironment(unittest.TestCase):
    def setUp(self):
        self.home = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.project = StubProject(Path(self.enterContext(tempfile.TemporaryDirectory())))
        self.session = SessionStart(self.home, self.project)

    def test_a_local_session_builds_nothing(self):
        self.project.setup_that_succeeds()
        result = self.session.run(remote=None)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse((self.home / LOG).exists())

    def test_a_cloud_session_without_an_environment_builds_it(self):
        self.project.setup_that_succeeds()
        result = self.session.run(remote="true")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(SETUP_RAN, (self.home / LOG).read_text())
        self.assertTrue((self.home / BUILT_MARK).exists())

    def test_a_cloud_session_with_a_built_environment_builds_nothing(self):
        self.project.setup_that_succeeds()
        (self.home / BUILT_MARK).parent.mkdir(parents=True)
        (self.home / BUILT_MARK).touch()
        result = self.session.run(remote="true")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse((self.home / LOG).exists())

    def test_a_failed_build_reports_the_end_of_its_log(self):
        self.project.setup_that_fails()
        result = self.session.run(remote="true")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("pypi.org did not answer", result.stderr)
        self.assertFalse((self.home / BUILT_MARK).exists())


class TestTheSessionStartHook(unittest.TestCase):
    def test_settings_run_the_start_script_when_a_session_starts(self):
        settings = json.loads((PROJECT_ROOT / ".claude" / "settings.json").read_text())
        commands = [hook["command"] for matcher in settings["hooks"]["SessionStart"] for hook in matcher["hooks"]]
        self.assertTrue(any(str(START_SCRIPT) in command for command in commands), commands)

    def test_the_setup_script_marks_the_environment_built_last(self):
        text = (PROJECT_ROOT / SETUP_SCRIPT).read_text()
        lines = text.splitlines()
        main_body = lines[lines.index("main() {") + 1:]
        self.assertIn(f'BUILT_MARK="$STATE_DIR/{BUILT_MARK.name}"', text)
        self.assertEqual('touch "$BUILT_MARK"', main_body[main_body.index("}") - 1].strip())


if __name__ == "__main__":
    unittest.main()
