from __future__ import annotations

from _health.readings import Alert, Sample

ALARMING_PRESSURES = ("critical",)
ALARMING_THERMAL_STATES = ("serious", "critical")


class PressureDetector:
    def alerts(self, sample: Sample, now: float) -> list[Alert]:
        pressure = sample.system.pressure
        if pressure not in ALARMING_PRESSURES:
            return []
        message = f"memory pressure {pressure}, {sample.system.available_mb:.0f} MB available"
        return [Alert(f"pressure:{pressure}", "pressure", message, now)]


class ThermalDetector:
    def alerts(self, sample: Sample, now: float) -> list[Alert]:
        thermal = sample.system.thermal
        if thermal not in ALARMING_THERMAL_STATES:
            return []
        return [Alert(f"thermal:{thermal}", "thermal", f"thermal state {thermal}", now)]
