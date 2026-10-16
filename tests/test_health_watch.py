from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from _health_fixtures import (
    AVAILABLE_MB, BASE_RSS_MB, DISK_FREE_GB, MINUTE, RecordingNotifier, ScriptedSampler, rss_series, sample, system,
)

import machine_health as health

GROWTH_MB_PER_MINUTE = 10.0
RETENTION_DAYS = 14
DAY = 86400.0


class WatchCase(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.settings = health.HealthSettings({}, Path(self._directory.name))
        self.notifier = RecordingNotifier()

    def watch(self, samples: list[health.Sample]) -> health.HealthWatch:
        detectors = [health.PressureDetector(), health.ThermalDetector()]
        return health.HealthWatch(self.settings, ScriptedSampler(samples), health.Alarm(detectors, [self.notifier]))

    def run_through(self, samples: list[health.Sample]) -> list[health.Alert]:
        watch = self.watch(samples)
        return [alert for each in samples for alert in watch.sample_once(each.taken_at)]


class TestCriticalPressureSeenOnConsecutiveSamples(WatchCase):
    def test_notifies_once_within_the_cooldown(self):
        samples = [sample(minute, reading=system(pressure="critical")) for minute in range(30)]
        self.assertEqual(1, len(self.run_through(samples)))
        self.assertEqual(1, len(self.notifier.messages))


class TestAnAlertRaised(WatchCase):
    def test_is_journaled_where_the_report_finds_it(self):
        alerts = self.run_through([sample(0, reading=system(pressure="critical"))])
        self.assertEqual(alerts, health.HealthJournals(self.settings).alerts_since(0.0))


class TestAnAlertSounded(unittest.TestCase):
    def test_reaches_every_notifier(self):
        notifiers = [RecordingNotifier(), RecordingNotifier()]
        alert = health.Alert("thermal:serious", "thermal", "thermal state serious", 0.0)
        health.Alarm([], notifiers).sound(alert)
        self.assertEqual([[alert.message]] * 2, [notifier.messages for notifier in notifiers])


class TestSamplesOlderThanTheRetention(WatchCase):
    def test_are_pruned_by_day(self):
        old, new = sample(0), sample(int(RETENTION_DAYS * DAY / MINUTE) + 2 * 24 * 60)
        self.run_through([old, new])
        days = sorted(path.stem for path in (self.settings.directory / "samples").iterdir())
        self.assertEqual([datetime.fromtimestamp(new.taken_at).date().isoformat()], days)


class TestAJournalLineCutShortByACrash(WatchCase):
    def test_is_skipped(self):
        journals = health.HealthJournals(self.settings)
        journals.samples.append(sample(0).as_dict(), sample(0).taken_at)
        path = next((self.settings.directory / "samples").iterdir())
        path.write_text(path.read_text() + '{"taken_at": 17', encoding="utf-8")
        self.assertEqual([sample(0)], journals.samples_since(0.0))


class TestWorkloadLabels(unittest.TestCase):
    def setUp(self) -> None:
        self.labels = health.WorkloadLabels()

    def test_a_model_server_module(self):
        self.assertEqual("model-server", self.labels.label(["python", "-m", "surya.ocr_error.server"], "Python"))

    def test_the_extract_script(self):
        arguments = ["python", ".claude/skills/extract-corpus/scripts/extract.py", "extract"]
        self.assertEqual("extract", self.labels.label(arguments, "Python"))

    def test_the_search_server(self):
        self.assertEqual("vault-rag", self.labels.label(["python", ".claude/skills/search/server.py"], "Python"))

    def test_ollama(self):
        self.assertEqual("ollama", self.labels.label(["/usr/local/bin/ollama", "serve"], "ollama"))

    def test_any_other_process_by_its_name(self):
        self.assertEqual("other:Safari", self.labels.label(["/Applications/Safari.app/Safari"], "Safari"))


class TestHealthReport(unittest.TestCase):
    def test_states_each_process_growth_per_hour(self):
        samples = rss_series(lambda minute: BASE_RSS_MB + GROWTH_MB_PER_MINUTE * minute)
        row = health.HealthReport(samples, []).as_dict()["processes"][0]
        self.assertEqual((1600, 600), (row["last_mb"], row["growth_mb_per_hour"]))

    def test_of_no_samples_says_so(self):
        self.assertEqual(0, health.HealthReport([], []).as_dict()["samples"])

    def test_names_the_worst_pressure(self):
        samples = [sample(0), sample(1, reading=system(pressure="warn")), sample(2)]
        self.assertEqual("warn", health.HealthReport(samples, []).as_dict()["system"]["worst_pressure"])

    def test_names_the_worst_thermal_state(self):
        serious = health.SystemReading(AVAILABLE_MB, 0.0, "normal", 1.0, DISK_FREE_GB, "serious")
        samples = [sample(0), sample(1, reading=serious), sample(2)]
        self.assertEqual("serious", health.HealthReport(samples, []).as_dict()["system"]["worst_thermal"])


class FixedThermalLevel(health.ThermalState):
    def __init__(self, level: int | None) -> None:
        self._fixed = level

    def _level(self) -> int | None:
        return self._fixed


class TestThermalState(unittest.TestCase):
    def test_names_the_level_the_system_reports(self):
        self.assertEqual("serious", FixedThermalLevel(2).reading())

    def test_a_machine_that_reports_no_level_has_no_thermal_state(self):
        self.assertIsNone(FixedThermalLevel(None).reading())

    def test_an_unknown_level_has_no_thermal_state(self):
        self.assertIsNone(FixedThermalLevel(7).reading())


class TestHealthSettings(unittest.TestCase):
    def test_machine_values_override_the_defaults(self):
        settings = health.HealthSettings({"health": {"alert_cooldown_minutes": 5}})
        self.assertEqual((300.0, 14 * DAY), (settings.alert_cooldown_seconds, settings.retention_seconds))

    def test_a_journal_line_from_before_the_thermal_state_reads_back(self):
        record = json.loads(json.dumps(sample(0).as_dict()))
        del record["system"]["thermal"]
        self.assertIsNone(health.Sample.from_dict(record).system.thermal)

    def test_samples_journal_round_trips(self):
        record = json.loads(json.dumps(sample(0).as_dict()))
        self.assertEqual(sample(0), health.Sample.from_dict(record))


if __name__ == "__main__":
    unittest.main()
