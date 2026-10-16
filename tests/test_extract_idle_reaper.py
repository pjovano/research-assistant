from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from surya_servers import IdleClock, IdleReaper

REAPED_PID = 4242
IDLE_SECONDS = 600.0
LAST_ACTIVE = 1000.0
MUCH_LATER = 9999.0


class FakeLogs:
    def __init__(self, last_active: float | None) -> None:
        self._last_active = last_active

    def last_active(self) -> float | None:
        return self._last_active


class FakeRun:
    def __init__(self, in_progress: bool) -> None:
        self._in_progress = in_progress

    def in_progress(self) -> bool:
        return self._in_progress


class FinishingRun:
    def __init__(self, answers: list[bool]) -> None:
        self._answers = answers

    def in_progress(self) -> bool:
        return self._answers.pop(0) if len(self._answers) > 1 else self._answers[0]


class LateStartingServers:
    def __init__(self) -> None:
        self._looked = False
        self._started = False

    def running(self) -> bool:
        self._started = self._looked
        self._looked = True
        return self._started

    @property
    def stopped_pids(self) -> list[int]:
        return [REAPED_PID] if self._started else []

    def stop_all(self) -> None:
        pass


class FakeServers:
    def __init__(self, running: bool = True) -> None:
        self._running = running
        self.stopped = False
        self.stopped_pids: list[int] = []

    def running(self) -> bool:
        return self._running

    def stop_all(self) -> None:
        self.stopped = True
        self._running = False
        self.stopped_pids = [REAPED_PID]


class TestIdleReaper(unittest.TestCase):
    def _reaper(self, last_active: float | None, in_progress: bool, servers=None):
        return IdleReaper(IdleClock(IDLE_SECONDS, FakeLogs(last_active)), run=FakeRun(in_progress),
                          servers=servers or FakeServers(), prefetch=FakeRun(False))

    def _reaped(self, reaper: IdleReaper, now: float) -> list[int]:
        reaper.reap_if_due(now)
        return reaper.stopped_pids

    def _watched(self, reaper: IdleReaper) -> list[int]:
        reaper.watch(poll_seconds=0.0)
        return reaper.stopped_pids

    def test_servers_idle_past_the_timeout_are_stopped(self) -> None:
        past_idle = LAST_ACTIVE + IDLE_SECONDS + 100.0
        self.assertEqual([REAPED_PID], self._reaped(self._reaper(LAST_ACTIVE, False), past_idle))

    def test_servers_used_within_the_timeout_are_left_alone(self) -> None:
        within = LAST_ACTIVE + IDLE_SECONDS - 200.0
        self.assertEqual([], self._reaped(self._reaper(LAST_ACTIVE, False), within))

    def test_servers_are_left_alone_while_an_extraction_is_running(self) -> None:
        self.assertEqual([], self._reaped(self._reaper(LAST_ACTIVE, True), MUCH_LATER))

    def test_watching_ends_when_no_server_remains_and_no_extraction_runs(self) -> None:
        servers = FakeServers(running=False)
        self.assertEqual([], self._watched(self._reaper(LAST_ACTIVE, False, servers)))
        self.assertFalse(servers.stopped)

    def test_watching_outlasts_the_wait_for_a_server_the_running_extraction_starts_later(self) -> None:
        reaper = IdleReaper(IdleClock(0.0, FakeLogs(0.0)), run=FinishingRun([True, True, False]),
                            servers=LateStartingServers(), prefetch=FakeRun(False))
        self.assertEqual([REAPED_PID], self._watched(reaper))

    def test_watching_ends_once_it_has_reaped(self) -> None:
        servers = FakeServers()
        reaper = IdleReaper(IdleClock(0.0, FakeLogs(0.0)), run=FakeRun(False), servers=servers, prefetch=FakeRun(False))
        self.assertEqual([REAPED_PID], self._watched(reaper))
        self.assertTrue(servers.stopped)


if __name__ == "__main__":
    unittest.main()
