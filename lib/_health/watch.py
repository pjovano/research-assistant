from __future__ import annotations

from typing import Protocol

from _health.journal import DailyJournal
from _health.readings import Alert, Sample
from _health.sampler import Sampler
from _health.settings import HealthSettings

TAKEN_AT = "taken_at"
RAISED_AT = "raised_at"


class Detector(Protocol):
    def alerts(self, sample: Sample, now: float) -> list[Alert]: ...


class Notifier(Protocol):
    def notify(self, alert: Alert) -> None: ...


class HealthJournals:
    def __init__(self, settings: HealthSettings) -> None:
        self.samples = DailyJournal(settings.directory / "samples")
        self.alerts = DailyJournal(settings.directory / "alerts")

    def samples_since(self, cutoff: float) -> list[Sample]:
        return [Sample.from_dict(record) for record in self.samples.records_since(cutoff, TAKEN_AT)]

    def alerts_since(self, cutoff: float) -> list[Alert]:
        return [Alert.from_dict(record) for record in self.alerts.records_since(cutoff, RAISED_AT)]

    def prune(self, cutoff: float) -> None:
        self.samples.prune(cutoff)
        self.alerts.prune(cutoff)


class Alarm:
    def __init__(self, detectors: list[Detector], notifiers: list[Notifier]) -> None:
        self._detectors = detectors
        self._notifiers = notifiers

    def detected(self, sample: Sample, now: float) -> list[Alert]:
        return [alert for detector in self._detectors for alert in detector.alerts(sample, now)]

    def sound(self, alert: Alert) -> None:
        for notifier in self._notifiers:
            notifier.notify(alert)


class HealthWatch:
    def __init__(self, settings: HealthSettings, sampler: Sampler, alarm: Alarm) -> None:
        self._settings = settings
        self._sampler = sampler
        self._alarm = alarm
        self._journals = HealthJournals(settings)

    def sample_once(self, now: float) -> list[Alert]:
        sample = self._sampler.sample(now)
        self._journals.samples.append(sample.as_dict(), now)
        self._journals.prune(now - self._settings.retention_seconds)
        fresh = self._fresh(self._alarm.detected(sample, now), now)
        for alert in fresh:
            self._raise(alert, now)
        return fresh

    def _fresh(self, alerts: list[Alert], now: float) -> list[Alert]:
        recent = {alert.key for alert in self._journals.alerts_since(now - self._settings.alert_cooldown_seconds)}
        return [alert for alert in alerts if alert.key not in recent]

    def _raise(self, alert: Alert, now: float) -> None:
        self._journals.alerts.append(alert.as_dict(), now)
        self._alarm.sound(alert)
