from __future__ import annotations

import threading
import time
from collections.abc import Callable

from engine_environment import EngineEnvironment
from surya_servers import ServerLogs, SuryaServers

SILENCE_LIMIT_SECONDS = 600.0
SILENCE_POLL_SECONDS = 5.0


class EngineUnresponsive(RuntimeError):
    def __init__(self, silence_limit_seconds: float, request_count: int) -> None:
        super().__init__(f"the engine's model servers wrote nothing for {silence_limit_seconds:.0f} seconds while "
                         f"{request_count} engine requests awaited them; the servers were stopped, and the next "
                         f"request starts a fresh one")


class FailedInferenceRequests(RuntimeError):
    def __init__(self, failed_count: int) -> None:
        super().__init__(f"{failed_count} engine requests failed after their retries, so the pages they carried came "
                         f"back blank; the conversion is refused: check that the model servers run, outside the "
                         f"sandbox, with Metal")


class PendingGeneration:
    def __init__(self, generate: Callable[[], list]) -> None:
        self._result: list = []
        self._failure: Exception | None = None
        self._thread = threading.Thread(target=self._run, args=(generate,), daemon=True)
        self._thread.start()

    def _run(self, generate: Callable[[], list]) -> None:
        try:
            self._result = generate()
        except Exception as failure:
            self._failure = failure

    def finished_within(self, seconds: float) -> bool:
        self._thread.join(seconds)
        return not self._thread.is_alive()

    def outcome(self) -> list:
        if self._failure is not None:
            raise self._failure
        return self._result


class SilenceWatch:
    def __init__(self, logs: ServerLogs | None = None, limit_seconds: float = SILENCE_LIMIT_SECONDS,
                 poll_seconds: float = SILENCE_POLL_SECONDS) -> None:
        self._logs = logs or ServerLogs()
        self.limit_seconds = limit_seconds
        self._poll_seconds = poll_seconds

    def fell_silent_during(self, pending: PendingGeneration) -> bool:
        started = time.time()
        while not pending.finished_within(self._poll_seconds):
            if self._silent_since(started):
                return True
        return False

    def _silent_since(self, started: float) -> bool:
        last_written = self._logs.last_active() or started
        last_heard = max(started, last_written)
        return time.time() - last_heard >= self.limit_seconds


class GuardedInferenceManager:
    def __init__(self, manager, watch: SilenceWatch | None = None, servers: SuryaServers | None = None) -> None:
        self._manager = manager
        self._watch = watch or SilenceWatch()
        self._servers = servers or SuryaServers()
        self.failed_requests = 0

    def generate(self, batch: list) -> list:
        pending = PendingGeneration(lambda: self._manager.generate(batch))
        if self._watch.fell_silent_during(pending):
            self._discard_servers()
            raise EngineUnresponsive(self._watch.limit_seconds, len(batch))
        outputs = pending.outcome()
        self.failed_requests += sum(1 for output in outputs if output.error)
        return outputs

    def _discard_servers(self) -> None:
        self._servers.stop_all()
        self._manager.stop()

    def start(self) -> None:
        self._manager.start()

    def stop(self) -> None:
        self._manager.stop()

    def capacity(self) -> int:
        return self._manager.capacity()


class RequestFailures:
    def __init__(self, manager: GuardedInferenceManager) -> None:
        self._manager = manager
        self._failed_before = 0

    def __enter__(self) -> RequestFailures:
        self._failed_before = self._manager.failed_requests
        return self

    def __exit__(self, exception_type, _exception, _traceback) -> None:
        failed_count = self._manager.failed_requests - self._failed_before
        if exception_type is None and failed_count:
            raise FailedInferenceRequests(failed_count)


class GuardedEngineModels:
    def created(self) -> dict:
        EngineEnvironment().apply()
        from marker.models import create_model_dict
        from surya.inference import SuryaInferenceManager
        return create_model_dict(inference_manager=GuardedInferenceManager(SuryaInferenceManager()))
