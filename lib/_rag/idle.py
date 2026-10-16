from __future__ import annotations

import functools
import threading
import time
from contextlib import contextmanager
from typing import Callable, Iterator

IDLE_RELEASE_SECONDS = 300.0
WATCH_POLL_SECONDS = 30.0

Release = Callable[[], None]


class IdleRelease:
    def __init__(self, releases: list[Release], idle_seconds: float = IDLE_RELEASE_SECONDS,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._releases = releases
        self._idle_seconds = idle_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._last_served: float | None = None

    def served(self, handler: Callable) -> Callable:
        @functools.wraps(handler)
        def serving_handler(*arguments, **keywords):
            with self._serving():
                return handler(*arguments, **keywords)
        return serving_handler

    def release_if_idle(self) -> None:
        with self._lock:
            if self._is_idle():
                self._release()

    def start_watching(self, poll_seconds: float = WATCH_POLL_SECONDS) -> None:
        threading.Thread(target=self._watch, args=(poll_seconds,), daemon=True).start()

    @contextmanager
    def _serving(self) -> Iterator[None]:
        with self._lock:
            try:
                yield
            finally:
                self._last_served = self._clock()

    def _watch(self, poll_seconds: float) -> None:
        while True:
            time.sleep(poll_seconds)
            self.release_if_idle()

    def _is_idle(self) -> bool:
        return self._last_served is not None and self._clock() - self._last_served >= self._idle_seconds

    def _release(self) -> None:
        for release in self._releases:
            release()
        self._last_served = None
