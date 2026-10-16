from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _health_fixtures import sample

import machine_health as health
from agent_core._ports.host import Level

BYTES_PER_MB = 1024 * 1024
SWAP_BYTES = 3 * BYTES_PER_MB + BYTES_PER_MB // 2


class FixedReadings:
    def __init__(self, memory: Level | None, thermal: Level | None, swap_bytes: int | None) -> None:
        self._memory = memory
        self._thermal = thermal
        self._swap_bytes = swap_bytes

    def memory_pressure(self) -> Level | None:
        return self._memory

    def thermal(self) -> Level | None:
        return self._thermal

    def swap_used(self) -> int | None:
        return self._swap_bytes


class ProbeCase(unittest.TestCase):
    def setUp(self) -> None:
        self.disk = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def reading(self, memory: Level | None = Level.NORMAL, thermal: Level | None = Level.NORMAL,
                swap_bytes: int | None = 0) -> health.SystemReading:
        return health.SystemProbes(self.disk, FixedReadings(memory, thermal, swap_bytes)).reading()


class TestThePressureSpelling(ProbeCase):
    def test_each_level_keeps_the_journals_spelling(self) -> None:
        spelled = {level: self.reading(memory=level).pressure for level in (Level.NORMAL, Level.ELEVATED,
                                                                              Level.CRITICAL)}
        self.assertEqual({Level.NORMAL: "normal", Level.ELEVATED: "warn", Level.CRITICAL: "critical"}, spelled)

    def test_an_unread_pressure_is_null(self) -> None:
        self.assertIsNone(self.reading(memory=None).pressure)


class TestTheThermalSpelling(ProbeCase):
    def test_each_level_keeps_the_journals_spelling(self) -> None:
        levels = (Level.NORMAL, Level.ELEVATED, Level.SERIOUS, Level.CRITICAL)
        self.assertEqual(["nominal", "fair", "serious", "critical"],
                         [self.reading(thermal=level).thermal for level in levels])

    def test_an_unread_thermal_state_is_null(self) -> None:
        self.assertIsNone(self.reading(thermal=None).thermal)


class TestTheSwapReading(ProbeCase):
    def test_is_journaled_in_megabytes(self) -> None:
        self.assertEqual(3.5, self.reading(swap_bytes=SWAP_BYTES).swap_used_mb)

    def test_an_unread_swap_is_null(self) -> None:
        self.assertIsNone(self.reading(swap_bytes=None).swap_used_mb)


class TestTheDetectorsOnTheCoresLevels(ProbeCase):
    def alert_keys(self, memory: Level, thermal: Level) -> list[str]:
        observed = sample(0, reading=self.reading(memory=memory, thermal=thermal))
        detectors = (health.PressureDetector(), health.ThermalDetector())
        return [alert.key for detector in detectors for alert in detector.alerts(observed, observed.taken_at)]

    def test_critical_pressure_and_serious_heat_raise_alerts(self) -> None:
        self.assertEqual(["pressure:critical", "thermal:serious"], self.alert_keys(Level.CRITICAL, Level.SERIOUS))

    def test_elevated_pressure_and_heat_raise_none(self) -> None:
        self.assertEqual([], self.alert_keys(Level.ELEVATED, Level.ELEVATED))


if __name__ == "__main__":
    unittest.main()
