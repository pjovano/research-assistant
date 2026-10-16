from __future__ import annotations

import argparse
import json
import os
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
from providers import Providers

USAGE_EXIT_CODE = 2
DEFAULT_REPORT_HOURS = 24.0
SECONDS_PER_HOUR = 3600

Command = Callable[[argparse.Namespace], int]


class HealthCli:
    def __init__(self, settings: health.HealthSettings, providers: Providers) -> None:
        self._settings = settings
        self._providers = providers
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
        health_job, scheduler = self._health_job(), self._providers.scheduler()()
        job = health_job.job()
        needed = health_job.script_exists and not scheduler.installed(job)
        if arguments.apply and needed:
            scheduler.install(job)
        self._print({"plist": scheduler.location(job), "needed": needed, "installed": arguments.apply and needed,
                     "contents": scheduler.definition(job), "manual": scheduler.manual_install(job)})
        return 0

    def _run_uninstall(self, arguments: argparse.Namespace) -> int:
        job, scheduler = self._health_job().job(), self._providers.scheduler()()
        installed = scheduler.installed(job)
        if arguments.apply:
            scheduler.remove(job)
        self._print({"label": job.label, "installed": installed, "removed": arguments.apply})
        return 0

    def _health_job(self) -> health.HealthJob:
        return health.HealthJob(health.HEALTH_SCRIPT, self._settings.directory / health.LOG_NAME)

    def _watch(self) -> health.HealthWatch:
        detectors = [health.PressureDetector(), health.ThermalDetector()]
        probes = health.SystemProbes(Path.home(), self._providers.system_readings()())
        sampler = health.Sampler(probes, health.WorkloadLabels(), self._settings.other_processes_kept)
        notifiers = [notifier(health.HEALTH_NOTICE_HEADING) for notifier in self._providers.notifier()]
        return health.HealthWatch(self._settings, sampler, health.Alarm(detectors, notifiers))

    def _build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="health.py")
        commands = parser.add_subparsers()
        self._command(commands, "sample", self._run_sample)
        report = self._command(commands, "report", self._run_report)
        report.add_argument("--hours", type=float, default=DEFAULT_REPORT_HOURS)
        for name, run in (("install", self._run_install), ("uninstall", self._run_uninstall)):
            self._command(commands, name, run).add_argument("--apply", action="store_true")
        return parser

    @staticmethod
    def _command(commands: argparse._SubParsersAction, name: str, run: Command) -> argparse.ArgumentParser:
        parser = commands.add_parser(name)
        parser.set_defaults(run=run)
        return parser

    @staticmethod
    def _print(report: dict) -> None:
        print(json.dumps(report, indent=2, ensure_ascii=False))


def main(argv: list[str]) -> int:
    machine = load_machine_config()
    return HealthCli(health.HealthSettings(machine), Providers.from_machine(machine, os.environ)).run(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
