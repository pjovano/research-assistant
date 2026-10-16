from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from pathlib import Path

import psutil

import vault
from engine_turn import TURN_NAME, WAITING_NAME, EngineTurn
from server_command_line import ServerCommandLine

SURYA_CACHE_DIR_KEY = "surya_cache_dir"
DEFAULT_SURYA_CACHE_DIR = Path.home() / ".cache" / "datalab" / "surya"


def surya_cache_dir(machine: dict) -> Path:
    value = machine.get(SURYA_CACHE_DIR_KEY)
    return Path(str(value)).expanduser() if value else DEFAULT_SURYA_CACHE_DIR


SENTINEL_DIR = surya_cache_dir(vault.MACHINE)
SENTINEL_SUFFIX = "_server.json"
LOG_SUFFIX = "_server.log"
TERMINATE_GRACE_SECONDS = 5.0
POLL_SECONDS = 0.2
IDLE_SECONDS = 300.0
WATCH_POLL_SECONDS = 30.0
RUN_NAME = "engine-run.json"
PREFETCH_RUN_NAME = "engine-prefetch.json"
RUN_PATH = vault.SCRATCH_DIR / RUN_NAME
REAPER_PATH = vault.SCRATCH_DIR / "engine-reaper.json"
MODEL_KEY = "model"


class SuryaServers:
    def __init__(self, processes: ServerProcesses | None = None) -> None:
        self._processes = processes or ServerProcesses()
        self._stopped_pids: list[int] = []

    @property
    def stopped_pids(self) -> list[int]:
        return list(self._stopped_pids)

    def stop_all(self) -> None:
        pids = self._recorded_pids() | set(self._processes.pids())
        self._clear_sentinels()
        live = [pid for pid in sorted(pids) if Process(pid).alive()]
        for pid in live:
            self._stop(Process(pid))
        self._stopped_pids = live

    def running(self) -> bool:
        return bool(self._sentinels()) or bool(self._processes.pids())

    def _recorded_pids(self) -> set[int]:
        pids = (PidFile(sentinel).pid() for sentinel in self._sentinels())
        return {pid for pid in pids if pid is not None}

    def _clear_sentinels(self) -> None:
        for sentinel in self._sentinels():
            sentinel.unlink(missing_ok=True)

    @staticmethod
    def _sentinels() -> list[Path]:
        return ServerRecords().paths()

    def _stop(self, process: Process) -> None:
        process.terminate()
        self._await_exit(process)

    @staticmethod
    def _await_exit(process: Process) -> None:
        deadline = time.monotonic() + TERMINATE_GRACE_SECONDS
        while time.monotonic() < deadline and process.alive():
            time.sleep(POLL_SECONDS)
        if process.alive():
            process.kill()


class ServerRecords:
    def paths(self) -> list[Path]:
        return sorted(SENTINEL_DIR.glob(f"*{SENTINEL_SUFFIX}"))

    def models(self) -> frozenset[str]:
        named = (self._model(path) for path in self.paths())
        return frozenset(model for model in named if model)

    @staticmethod
    def _model(path: Path) -> str | None:
        try:
            return json.loads(path.read_text(encoding="utf-8")).get(MODEL_KEY)
        except (OSError, ValueError):
            return None


class ServerProcesses:
    def __init__(self, command_line: ServerCommandLine | None = None) -> None:
        self._command_line = command_line

    def pids(self) -> list[int]:
        command_line = self._command_line or ServerCommandLine(ServerRecords().models())
        return sorted(process.pid for process in psutil.process_iter() if self._serves(process, command_line))

    @staticmethod
    def _serves(process: psutil.Process, command_line: ServerCommandLine) -> bool:
        try:
            return command_line.matches(process.cmdline())
        except psutil.Error:
            return False


class Process:
    def __init__(self, pid: int) -> None:
        self._pid = pid

    def alive(self) -> bool:
        try:
            return psutil.Process(self._pid).status() != psutil.STATUS_ZOMBIE
        except psutil.Error:
            return False

    def terminate(self) -> None:
        self._signal(signal.SIGTERM)

    def kill(self) -> None:
        self._signal(signal.SIGKILL)

    def _signal(self, number: int) -> None:
        try:
            os.kill(self._pid, number)
        except (ProcessLookupError, PermissionError):
            return


class PidFile:
    def __init__(self, path: Path) -> None:
        self._path = path

    def pid(self) -> int | None:
        try:
            pid = json.loads(self._path.read_text(encoding="utf-8")).get("pid")
        except (OSError, ValueError):
            return None
        return int(pid) if pid else None

    def write(self, pid: int) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps({"pid": pid}), encoding="utf-8")

    def clear(self) -> None:
        self._path.unlink(missing_ok=True)

    def names_a_live_process(self) -> bool:
        pid = self.pid()
        return pid is not None and Process(pid).alive()


class ServerLogs:
    def last_active(self) -> float | None:
        written = [path.stat().st_mtime for path in SENTINEL_DIR.glob(f"*{LOG_SUFFIX}")]
        return max(written) if written else None


class EngineRun:
    def __init__(self, path: Path | None = None, turn: EngineTurn | None = None, servers_agreement=None) -> None:
        path = path or vault.SCRATCH_DIR / RUN_NAME
        self._file = PidFile(path)
        self._turn = turn or EngineTurn(path.parent / TURN_NAME, path.parent / WAITING_NAME)
        self._servers_agreement = servers_agreement

    def started(self) -> None:
        self._turn.take()
        if self._servers_agreement is not None:
            self._servers_agreement.settle()
        self._file.write(os.getpid())

    def finished(self) -> None:
        self._file.clear()
        self._turn.give_back()

    def in_progress(self) -> bool:
        return self._file.names_a_live_process()


class IdleClock:
    def __init__(self, idle_seconds: float = IDLE_SECONDS, logs: ServerLogs | None = None) -> None:
        self._idle_seconds = idle_seconds
        self._logs = logs or ServerLogs()

    def is_idle(self, now: float) -> bool:
        last_active = self._logs.last_active()
        return last_active is not None and now - last_active >= self._idle_seconds


class IdleReaper:
    def __init__(self, clock: IdleClock | None = None, run: EngineRun | None = None,
                 servers: SuryaServers | None = None, prefetch: EngineRun | None = None) -> None:
        self._clock = clock or IdleClock()
        self._runs = [run or EngineRun(), prefetch or EngineRun(vault.SCRATCH_DIR / PREFETCH_RUN_NAME)]
        self._servers = servers or SuryaServers()

    def is_due(self, now: float) -> bool:
        if self._converting():
            return False
        return self._clock.is_idle(now)

    def _converting(self) -> bool:
        return any(run.in_progress() for run in self._runs)

    @property
    def stopped_pids(self) -> list[int]:
        return self._servers.stopped_pids

    def reap_if_due(self, now: float) -> None:
        if self.is_due(now):
            self._servers.stop_all()

    def watch(self, poll_seconds: float = WATCH_POLL_SECONDS) -> None:
        while self._has_servers_to_watch():
            self.reap_if_due(time.time())
            if self.stopped_pids:
                return
            time.sleep(poll_seconds)

    def _has_servers_to_watch(self) -> bool:
        return self._servers.running() or self._converting()


class DetachedLauncher:
    def launch(self, command: list[str]) -> subprocess.Popen:
        return subprocess.Popen(command, start_new_session=True,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class ReaperProcess:
    def __init__(self, path: Path = REAPER_PATH, launcher: DetachedLauncher | None = None) -> None:
        self._file = PidFile(path)
        self._launcher = launcher or DetachedLauncher()

    def ensure_running(self, command: list[str]) -> None:
        if self._file.names_a_live_process():
            return
        self._file.write(self._launcher.launch(command).pid)
