from __future__ import annotations

import plistlib
import subprocess
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import machine_health as health
from _health.hook import HealthWatcherHook

STAGE_COMMAND = "~/.research-vault/venv/bin/python .claude/skills/extract-corpus/scripts/extract.py status"
OTHER_COMMAND = "git status --porcelain"
FORMER_CHECKOUTS_LABEL = "com.research-vault.machine-health"


class FakeLaunchctl:
    def __init__(self, loaded: bool, bootstrap_fails: bool = False) -> None:
        self.loaded = loaded
        self.bootstrap_fails = bootstrap_fails
        self.calls: list[str] = []
        self.addressed: list[str] = []

    def run(self, arguments: list[str]) -> subprocess.CompletedProcess:
        self.calls.append(arguments[0])
        self.addressed.extend(arguments[1:])
        return subprocess.CompletedProcess(arguments, self._returncode(arguments[0]), "", "refused")

    def _returncode(self, verb: str) -> int:
        if verb == "bootstrap":
            self.loaded = not self.bootstrap_fails
            return 1 if self.bootstrap_fails else 0
        if verb == "bootout":
            self.loaded = False
        return 0 if self.loaded or verb == "bootout" else 1


class InstallerCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.script = directory / "health.py"
        self.script.write_text("", encoding="utf-8")
        self.agent = health.LaunchAgent(self.script, directory / "launchd.log", directory / "agent.plist")

    def installer(self, launchctl: FakeLaunchctl) -> health.LaunchAgentInstaller:
        return health.LaunchAgentInstaller(self.agent, health.Launchctl(launchctl.run))

    def hook(self, launchctl: FakeLaunchctl, platform: str = "darwin") -> HealthWatcherHook:
        return HealthWatcherHook(self.installer(launchctl), platform)


class TestTheLaunchAgent(InstallerCase):
    def test_runs_the_sample_command_every_minute(self):
        contents = plistlib.loads(self.agent.contents())
        self.assertEqual(([str(self.script), "sample"], 60),
                         (contents["ProgramArguments"][1:], contents["StartInterval"]))


class TestAPipelineCommandOnAMachineWithoutTheWatcher(InstallerCase):
    def test_writes_and_loads_the_launch_agent(self):
        launchctl = FakeLaunchctl(loaded=False)
        report = self.hook(launchctl).report(STAGE_COMMAND)
        self.assertIn("Started the health watcher", report["systemMessage"])
        self.assertTrue(self.agent.is_current() and launchctl.loaded)


class TestAPipelineCommandWhileTheWatcherRuns(InstallerCase):
    def test_changes_nothing(self):
        launchctl = FakeLaunchctl(loaded=True)
        self.agent.write()
        self.assertIsNone(self.hook(launchctl).report(STAGE_COMMAND))
        self.assertEqual(["print"], launchctl.calls)


class TestAPipelineCommandWhileAStaleLaunchAgentIsLoaded(InstallerCase):
    def test_rewrites_and_reloads_it(self):
        launchctl = FakeLaunchctl(loaded=True)
        self.agent.path.write_bytes(b"stale")
        self.hook(launchctl).report(STAGE_COMMAND)
        self.assertTrue(self.agent.is_current())
        self.assertEqual(["bootout", "print", "bootstrap"], launchctl.calls)


class TestAPipelineCommandBesideTheFormerCheckoutsJob(InstallerCase):
    def test_writes_a_launch_agent_of_its_own(self):
        own_agent = health.LaunchAgent(self.script, self.agent.path.with_name("launchd.log"))
        self.assertNotEqual(f"{FORMER_CHECKOUTS_LABEL}.plist", own_agent.path.name)

    def test_addresses_no_launchd_job_of_the_former_checkout(self):
        launchctl = FakeLaunchctl(loaded=True)
        self.agent.path.write_bytes(b"stale")
        self.hook(launchctl).report(STAGE_COMMAND)
        self.assertEqual([], [argument for argument in launchctl.addressed if FORMER_CHECKOUTS_LABEL in argument])


class TestACommandOutsideThePipeline(InstallerCase):
    def test_installs_nothing(self):
        launchctl = FakeLaunchctl(loaded=False)
        self.assertIsNone(self.hook(launchctl).report(OTHER_COMMAND))
        self.assertEqual([], launchctl.calls)


class TestAPipelineCommandOffMacOs(InstallerCase):
    def test_installs_nothing(self):
        launchctl = FakeLaunchctl(loaded=False)
        self.assertIsNone(self.hook(launchctl, platform="linux").report(STAGE_COMMAND))
        self.assertEqual([], launchctl.calls)


class TestAPipelineCommandWhenTheCheckoutLacksTheWatcherScript(InstallerCase):
    def test_installs_nothing(self):
        launchctl = FakeLaunchctl(loaded=False)
        self.script.unlink()
        self.assertIsNone(self.hook(launchctl).report(STAGE_COMMAND))
        self.assertFalse(self.agent.path.exists())


class TestALaunchAgentLaunchdRefuses(InstallerCase):
    def test_reports_without_blocking(self):
        report = self.hook(FakeLaunchctl(loaded=False, bootstrap_fails=True)).report(STAGE_COMMAND)
        self.assertIn("did not start", report["systemMessage"])
        self.assertNotIn("hookSpecificOutput", report)


if __name__ == "__main__":
    unittest.main()
