from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Callable


def _lib_dir() -> Path:
    here = Path(__file__).resolve()
    return next(parent / "lib" for parent in here.parents if (parent / "lib" / "vault.py").is_file())


sys.path.insert(0, str(_lib_dir()))
import machine_health as health
from _vault.machine import load_machine_config

USAGE_EXIT_CODE = 2
DEFAULT_REPORT_HOURS = 24.0
SECONDS_PER_HOUR = 3600
LOG_NAME = "launchd.log"

Command = Callable[[argparse.Namespace], int]


class HealthCli:
    def __init__(self, settings: health.HealthSettings) -> None:
        self._settings = settings
        self._journals = health.HealthJournals(settings)
        self._parser = self._build_parser()

    def run(self, argv: list[str]) -> int:
        if not argv:
            self._parser.print_help()
            return USAGE_EXIT_CODE
        arguments = self._parser.parse_args(argv)
        return arguments.run(arguments)

    def _run_sample(self, _arguments: argparse.Namespace) -> int:
        self._watch().sample_once(time.time())
        return 0

    def _run_report(self, arguments: argparse.Namespace) -> int:
        cutoff = time.time() - arguments.hours * SECONDS_PER_HOUR
        report = health.HealthReport(self._journals.samples_since(cutoff), self._journals.alerts_since(cutoff))
        self._print(report.as_dict())
        return 0

    def _run_install(self, arguments: argparse.Namespace) -> int:
        agent = health.LaunchAgent(health.HEALTH_SCRIPT, self._settings.directory / LOG_NAME)
        installer = health.LaunchAgentInstaller(agent, health.Launchctl())
        needed = installer.needs_install()
        if arguments.apply and needed:
            installer.install()
        self._print({"plist": str(agent.path), "needed": needed, "installed": arguments.apply and needed,
                     "contents": agent.contents().decode(), "manual": agent.bootstrap_command()})
        return 0

    def _watch(self) -> health.HealthWatch:
        detectors = [health.PressureDetector(), health.ThermalDetector()]
        sampler = health.Sampler(health.SystemProbes(Path.home()), health.WorkloadLabels(),
                                 self._settings.other_processes_kept)
        notifiers = [health.DesktopNotifier(), health.RemindersNotifier()]
        return health.HealthWatch(self._settings, sampler, health.Alarm(detectors, notifiers))

    def _build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="health.py")
        commands = parser.add_subparsers()
        self._command(commands, "sample", self._run_sample)
        report = self._command(commands, "report", self._run_report)
        report.add_argument("--hours", type=float, default=DEFAULT_REPORT_HOURS)
        install = self._command(commands, "install", self._run_install)
        install.add_argument("--apply", action="store_true")
        return parser

    @staticmethod
    def _command(commands: argparse._SubParsersAction, name: str, run: Command) -> argparse.ArgumentParser:
        parser = commands.add_parser(name)
        parser.set_defaults(run=run)
        return parser

    @staticmethod
    def _print(report: dict) -> None:
        print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(HealthCli(health.HealthSettings(load_machine_config())).run(sys.argv[1:]))
