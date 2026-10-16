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


class StubPrograms:
    LOGGED_STUB = '#!/bin/sh\necho "$(basename "$0") $*" >> "$STUB_CALLS"\n'
    UV_STUB = LOGGED_STUB + (
        'if [ "$1" = venv ]; then\n'
        '  mkdir -p "$4/bin"\n'
        '  printf \'#!/bin/sh\\necho "python $*" >> "$STUB_CALLS"\\n\' > "$4/bin/python"\n'
        '  chmod +x "$4/bin/python"\n'
        'fi\n'
        'if [ "$1" = pip ]; then exit "${STUB_SYNC_EXIT:-0}"; fi\n')
    CURL_STUB = LOGGED_STUB + 'exit "${STUB_CURL_EXIT:-0}"\n'
    PLAIN_PROGRAMS = ("dpkg", "node")

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.calls = directory / "calls.log"
        self._write("uv", self.UV_STUB)
        self._write("curl", self.CURL_STUB)
        for program in self.PLAIN_PROGRAMS:
            self._write(program, self.LOGGED_STUB)

    def _write(self, program: str, body: str) -> None:
        stub = self.directory / program
        stub.write_text(body)
        stub.chmod(0o755)

    def called(self, command: str) -> bool:
        return self.calls.exists() and any(line.startswith(command) for line in self.calls.read_text().splitlines())


class CloudSetup:
    SYSTEM_PATH = "/usr/bin:/bin"

    def __init__(self, home: Path, programs: StubPrograms) -> None:
        self._home = home
        self._programs = programs

    def run(self, **failures: str) -> subprocess.CompletedProcess:
        environment = {key: value for key, value in os.environ.items() if key != "CCR_AGENT_PROXY_CA_CERT_B64"}
        environment.update(HOME=str(self._home), STUB_CALLS=str(self._programs.calls),
                           PATH=f"{self._programs.directory}:{self.SYSTEM_PATH}", **failures)
        return subprocess.run(["bash", str(PROJECT_ROOT / SETUP_SCRIPT)], capture_output=True, text=True,
                              env=environment)


class TestAFailedSetupStepStopsOnlyTheStepsThatNeedIt(unittest.TestCase):
    MACHINE_CONFIG = Path(".research-vault/machine.json")
    FAILING_EXIT = "1"

    def setUp(self):
        self.home = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.programs = StubPrograms(Path(self.enterContext(tempfile.TemporaryDirectory())))
        self.setup = CloudSetup(self.home, self.programs)

    def test_a_failed_sync_still_points_at_the_empty_vault(self):
        self.setup.run(STUB_SYNC_EXIT=self.FAILING_EXIT)
        self.assertTrue((self.home / self.MACHINE_CONFIG).exists())

    def test_a_failed_sync_still_installs_pandoc(self):
        self.setup.run(STUB_SYNC_EXIT=self.FAILING_EXIT)
        self.assertTrue(self.programs.called("dpkg -i"))

    def test_a_failed_sync_skips_the_tokenizer_that_needs_the_venv(self):
        self.setup.run(STUB_SYNC_EXIT=self.FAILING_EXIT)
        self.assertFalse(self.programs.called("python"))

    def test_a_failed_pandoc_download_still_builds_the_venv(self):
        self.setup.run(STUB_CURL_EXIT=self.FAILING_EXIT)
        self.assertTrue(self.programs.called("uv pip sync"))

    def test_a_failed_step_leaves_the_environment_unbuilt_and_names_the_step(self):
        result = self.setup.run(STUB_SYNC_EXIT=self.FAILING_EXIT)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("build_python_environment", result.stderr)
        self.assertFalse((self.home / BUILT_MARK).exists())

    def test_a_setup_whose_steps_all_pass_marks_the_environment_built(self):
        result = self.setup.run()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue((self.home / BUILT_MARK).exists())


if __name__ == "__main__":
    unittest.main()
