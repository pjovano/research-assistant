from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import health as health_script
import machine_health as health
import providers
from agent_core._adapters.host.launchd import Launchctl, LaunchdScheduler
from agent_core._ports.host import Job
from providers import Providers

FAKE_ADAPTER = "fake"
FORMER_CHECKOUTS_LABEL = "com.research-vault.machine-health"
INSTALL_REPORT_KEYS = ["plist", "needed", "installed", "contents", "manual"]
NOT_LOADED = 113


class RecordingScheduler:
    def __init__(self, installed_labels: tuple[str, ...] = ()) -> None:
        self._installed = set(installed_labels)
        self.installs: list[str] = []
        self.removals: list[str] = []

    def install(self, job: Job) -> None:
        self.installs.append(job.label)
        self._installed.add(job.label)

    def installed(self, job: Job) -> bool:
        return job.label in self._installed

    def remove(self, job: Job) -> None:
        self.removals.append(job.label)
        self._installed.discard(job.label)

    def location(self, job: Job) -> str:
        return f"jobs/{job.label}"

    def definition(self, job: Job) -> str:
        return f"definition of {job.label}"

    def manual_install(self, job: Job) -> str:
        return f"install {job.label} by hand"


class GivenScheduler:
    def __init__(self, scheduler: RecordingScheduler) -> None:
        self._scheduler = scheduler

    def load(self):
        return lambda: self._scheduler


class HealthCliCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.settings = health.HealthSettings({}, directory)

    def run_cli(self, scheduler, *argv: str) -> dict:
        built = Providers({providers.SCHEDULER: {"adapter": FAKE_ADAPTER}}, {},
                          {providers.SCHEDULER: {FAKE_ADAPTER: GivenScheduler(scheduler)}})
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            health_script.HealthCli(self.settings, built).run(list(argv))
        return json.loads(printed.getvalue())


class TestUninstall(HealthCliCase):
    def test_the_read_only_form_names_the_health_job_alone_and_removes_nothing(self) -> None:
        scheduler = RecordingScheduler(installed_labels=(health.AGENT_LABEL,))
        report = self.run_cli(scheduler, "uninstall")
        self.assertEqual({"label": health.AGENT_LABEL, "installed": True, "removed": False}, report)
        self.assertEqual([], scheduler.removals)

    def test_the_read_only_form_never_names_the_former_checkouts_job(self) -> None:
        report = self.run_cli(RecordingScheduler(), "uninstall")
        self.assertNotIn(FORMER_CHECKOUTS_LABEL, json.dumps(report))

    def test_apply_removes_the_health_job_through_the_scheduler(self) -> None:
        scheduler = RecordingScheduler(installed_labels=(health.AGENT_LABEL,))
        report = self.run_cli(scheduler, "uninstall", "--apply")
        self.assertEqual(([health.AGENT_LABEL], True), (scheduler.removals, report["removed"]))


class TestInstall(HealthCliCase):
    def test_the_read_only_form_prints_the_definition_and_installs_nothing(self) -> None:
        scheduler = RecordingScheduler()
        report = self.run_cli(scheduler, "install")
        self.assertEqual((f"definition of {health.AGENT_LABEL}", []), (report["contents"], scheduler.installs))

    def test_the_read_only_form_prints_where_the_scheduler_keeps_the_definition(self) -> None:
        report = self.run_cli(RecordingScheduler(), "install")
        self.assertEqual(f"jobs/{health.AGENT_LABEL}", report["plist"])

    def test_the_read_only_form_prints_the_manual_command(self) -> None:
        report = self.run_cli(RecordingScheduler(), "install")
        self.assertEqual(f"install {health.AGENT_LABEL} by hand", report["manual"])



class TestInstallOnLaunchd(HealthCliCase):
    def setUp(self) -> None:
        super().setUp()
        self.plist_directory = Path(self.enterContext(tempfile.TemporaryDirectory())) / "LaunchAgents"
        self.scheduler = LaunchdScheduler(self.plist_directory, Launchctl(self.not_loaded))

    @staticmethod
    def not_loaded(arguments: list[str]) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(arguments, NOT_LOADED, "", "")

    def test_the_report_keeps_the_former_launch_agents_keys_in_order(self) -> None:
        self.assertEqual(INSTALL_REPORT_KEYS, list(self.run_cli(self.scheduler, "install")))

    def test_the_report_names_the_launch_agents_plist_path(self) -> None:
        expected = str(self.plist_directory / f"{health.AGENT_LABEL}.plist")
        self.assertEqual(expected, self.run_cli(self.scheduler, "install")["plist"])


if __name__ == "__main__":
    unittest.main()
