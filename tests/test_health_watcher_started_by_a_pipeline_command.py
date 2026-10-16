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
from agent_core._adapters.host.launchd import Launchctl, LaunchdScheduler

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
        self.plist_directory = directory / "LaunchAgents"
        self.health_job = health.HealthJob(self.script, directory / "launchd.log")
        self.plist = self.plist_directory / f"{health.AGENT_LABEL}.plist"

    def scheduler(self, launchctl: FakeLaunchctl) -> LaunchdScheduler:
        return LaunchdScheduler(self.plist_directory, Launchctl(launchctl.run))

    def hook(self, launchctl: FakeLaunchctl, platform: str = "darwin") -> HealthWatcherHook:
        return HealthWatcherHook(self.scheduler(launchctl), self.health_job, platform)

    def plist_is_current(self) -> bool:
        return self.plist.is_file() and self.plist.read_text(encoding="utf-8") == self.definition()

    def definition(self) -> str:
        return self.scheduler(FakeLaunchctl(loaded=False)).definition(self.health_job.job())

    def write_current_plist(self) -> None:
        self.plist_directory.mkdir(parents=True, exist_ok=True)
        self.plist.write_text(self.definition(), encoding="utf-8")


class TestTheHealthJob(InstallerCase):
    def test_runs_the_sample_command_every_minute(self):
        contents = plistlib.loads(self.definition().encode())
        self.assertEqual(([str(self.script), "sample"], 60),
                         (contents["ProgramArguments"][1:], contents["StartInterval"]))


class TestAPipelineCommandOnAMachineWithoutTheWatcher(InstallerCase):
    def test_writes_and_loads_the_launch_agent(self):
        launchctl = FakeLaunchctl(loaded=False)
        report = self.hook(launchctl).report(STAGE_COMMAND)
        self.assertIn("Started the health watcher", report["systemMessage"])
        self.assertTrue(self.plist_is_current() and launchctl.loaded)


class TestAPipelineCommandWhileTheWatcherRuns(InstallerCase):
    def test_changes_nothing(self):
        launchctl = FakeLaunchctl(loaded=True)
        self.write_current_plist()
        self.assertIsNone(self.hook(launchctl).report(STAGE_COMMAND))
        self.assertEqual(["print"], launchctl.calls)


class TestAPipelineCommandWhileAStaleLaunchAgentIsLoaded(InstallerCase):
    def test_rewrites_and_reloads_it(self):
        launchctl = FakeLaunchctl(loaded=True)
        self.plist_directory.mkdir(parents=True)
        self.plist.write_bytes(b"stale")
        self.hook(launchctl).report(STAGE_COMMAND)
        self.assertTrue(self.plist_is_current())
        self.assertEqual(["bootout", "print", "bootstrap"], launchctl.calls)


class TestAPipelineCommandBesideTheFormerCheckoutsJob(InstallerCase):
    def test_writes_a_launch_agent_of_its_own(self):
        self.assertNotEqual(FORMER_CHECKOUTS_LABEL, self.health_job.job().label)

    def test_addresses_no_launchd_job_of_the_former_checkout(self):
        launchctl = FakeLaunchctl(loaded=True)
        self.plist_directory.mkdir(parents=True)
        self.plist.write_bytes(b"stale")
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
        self.assertFalse(self.plist.exists())


class TestALaunchAgentLaunchdRefuses(InstallerCase):
    def test_reports_without_blocking(self):
        report = self.hook(FakeLaunchctl(loaded=False, bootstrap_fails=True)).report(STAGE_COMMAND)
        self.assertIn("did not start", report["systemMessage"])
        self.assertNotIn("hookSpecificOutput", report)


if __name__ == "__main__":
    unittest.main()
