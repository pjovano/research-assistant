from __future__ import annotations

import unittest

from _health_fixtures import sample, system

import machine_health as health


def keys(detector, reading: health.SystemReading) -> list[str]:
    observed = sample(0, reading=reading)
    return [alert.key for alert in detector.alerts(observed, observed.taken_at)]


class TestMemoryPressure(unittest.TestCase):
    def pressure_keys(self, pressure: str | None) -> list[str]:
        return keys(health.PressureDetector(), system(pressure=pressure))

    def test_critical_raises_an_alert(self):
        self.assertEqual(["pressure:critical"], self.pressure_keys("critical"))

    def test_warn_raises_nothing(self):
        self.assertEqual([], self.pressure_keys("warn"))

    def test_normal_raises_nothing(self):
        self.assertEqual([], self.pressure_keys("normal"))

    def test_an_unread_pressure_raises_nothing(self):
        self.assertEqual([], self.pressure_keys(None))


class TestThermalState(unittest.TestCase):
    def thermal_keys(self, thermal: str | None) -> list[str]:
        return keys(health.ThermalDetector(), system(thermal=thermal))

    def test_serious_raises_an_alert(self):
        self.assertEqual(["thermal:serious"], self.thermal_keys("serious"))

    def test_critical_raises_an_alert(self):
        self.assertEqual(["thermal:critical"], self.thermal_keys("critical"))

    def test_fair_raises_nothing(self):
        self.assertEqual([], self.thermal_keys("fair"))

    def test_nominal_raises_nothing(self):
        self.assertEqual([], self.thermal_keys("nominal"))

    def test_an_unread_thermal_state_raises_nothing(self):
        self.assertEqual([], self.thermal_keys(None))


if __name__ == "__main__":
    unittest.main()
