from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

import vault
from surya_servers import SENTINEL_DIR, SuryaServers

ENGINE_SLOTS_KEY = "engine_slots"
PARALLEL_VARIABLE = "SURYA_INFERENCE_PARALLEL"
ENGINE_DEFAULT_SLOTS = 8
VLM_SENTINEL_NAME = "llamacpp_server.json"
PORT_FIELD = "port"
SERVER_HOST = "127.0.0.1"
PROPS_PATH = "/props"
TOTAL_SLOTS_FIELD = "total_slots"
PROBE_TIMEOUT_SECONDS = 5.0


class EngineSlotsInvalid(ValueError):
    pass


class EngineSlots:
    def __init__(self, machine: dict) -> None:
        self._value = machine.get(ENGINE_SLOTS_KEY)

    def configured(self) -> int | None:
        if self._value is None:
            return None
        if isinstance(self._value, bool) or not isinstance(self._value, int) or self._value < 1:
            raise EngineSlotsInvalid(f"machine.json's {ENGINE_SLOTS_KEY} must be a positive whole number, "
                                     f"not {self._value!r}")
        return self._value

    def wanted(self) -> int:
        return self.configured() or ENGINE_DEFAULT_SLOTS


class RunningSlots:
    def __init__(self, sentinel_dir: Path, fetch: Callable[[str], dict] | None = None) -> None:
        self._sentinel = sentinel_dir / VLM_SENTINEL_NAME
        self._fetch = fetch or _fetched_json

    def count(self) -> int | None:
        port = self._port()
        if port is None:
            return None
        try:
            slots = self._fetch(f"http://{SERVER_HOST}:{port}{PROPS_PATH}").get(TOTAL_SLOTS_FIELD)
        except (OSError, ValueError, urllib.error.URLError):
            return None
        return slots if isinstance(slots, int) else None

    def _port(self) -> int | None:
        try:
            port = json.loads(self._sentinel.read_text(encoding="utf-8")).get(PORT_FIELD)
        except (OSError, ValueError):
            return None
        return port if isinstance(port, int) else None


def _fetched_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=PROBE_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


class SlotsAgreement:
    def __init__(self, slots: EngineSlots, running: RunningSlots, stop_servers: Callable[[], None]) -> None:
        self._slots = slots
        self._running = running
        self._stop_servers = stop_servers

    @classmethod
    def on_this_machine(cls) -> SlotsAgreement:
        return cls(EngineSlots(vault.MACHINE), RunningSlots(SENTINEL_DIR), lambda: SuryaServers().stop_all())

    def settle(self) -> None:
        running = self._running.count()
        if running is not None and running != self._slots.wanted():
            self._stop_servers()
