from __future__ import annotations

import subprocess
import threading
import time
from collections import deque
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, TextIO

import requests

from .settings import RERANKER_MODEL_KEY, MachineSettings

RERANK_PATH = "/v1/rerank"
HEALTH_PATH = "/health"
LLAMA_SERVER_HOST = "127.0.0.1"
LLAMA_SERVER_PORT = 8790
HEALTH_TIMEOUT_SECONDS = 60
HEALTH_POLL_SECONDS = 0.5
HEALTH_REQUEST_TIMEOUT_SECONDS = 2
RERANK_TIMEOUT_SECONDS = 120
STOP_TIMEOUT_SECONDS = 10
RERANK_MODEL_NAME = "reranker"
PROBE_QUERY = "Which philosopher wrote the Science of Logic?"
PROBE_MATCHING_PASSAGE = "Hegel published the Science of Logic between 1812 and 1816, in three volumes."
PROBE_UNRELATED_PASSAGE = "Knead the dough for ten minutes, then leave it to rise in a warm place."
DEGENERATE_SCORE_MAGNITUDE = 1e-6
STDERR_TAIL_LINES = 20
STDERR_JOIN_SECONDS = 1.0
PROBE_FAILED = "reranker probe failed"


class RerankerUnavailable(RuntimeError):
    pass


class HttpTransport:
    def __init__(self, session: requests.Session | None = None) -> None:
        self._session = session or requests.Session()

    def healthy(self, url: str) -> bool:
        try:
            return self._session.get(url + HEALTH_PATH, timeout=HEALTH_REQUEST_TIMEOUT_SECONDS).ok
        except requests.RequestException:
            return False

    def rerank(self, url: str, payload: dict) -> dict:
        try:
            return self._posted(url + RERANK_PATH, payload)
        except (requests.RequestException, ValueError) as error:
            raise RerankerUnavailable(f"rerank request to {url} failed: {type(error).__name__}: {error}") from error

    def _posted(self, url: str, payload: dict) -> dict:
        response = self._session.post(url, json=payload, timeout=RERANK_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()


class ProcessControl:
    def launch(self, command: list[str]) -> subprocess.Popen:
        return subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def now(self) -> float:
        return time.monotonic()


class _StderrTail:
    def __init__(self, stream: TextIO | None) -> None:
        self._lines: deque[str] = deque(maxlen=STDERR_TAIL_LINES)
        self._drain = threading.Thread(target=self._read, args=(stream,), daemon=True)
        self._drain.start()

    def _read(self, stream: TextIO | None) -> None:
        for line in stream or ():
            self._lines.append(line.rstrip("\n"))

    def quoted(self) -> str:
        self._drain.join(STDERR_JOIN_SECONDS)
        return "\n".join(self._lines)


class _StartingProcess:
    def __init__(self, process: subprocess.Popen) -> None:
        self._process = process
        self._tail = _StderrTail(process.stderr)

    def exited(self) -> bool:
        return self._process.poll() is not None

    def exit_report(self) -> str:
        return f"exited with status {self._process.returncode} before serving:\n{self._tail.quoted()}"


class LlamaServerProcess:
    def __init__(self, settings: MachineSettings, transport: HttpTransport, control: ProcessControl) -> None:
        self._settings = settings
        self._transport = transport
        self._control = control
        self._process: subprocess.Popen | None = None

    @staticmethod
    def on_this_machine() -> "LlamaServerProcess":
        return LlamaServerProcess(MachineSettings(), HttpTransport(), ProcessControl())

    @property
    def url(self) -> str:
        return f"http://{LLAMA_SERVER_HOST}:{LLAMA_SERVER_PORT}"

    @property
    def model(self) -> Path | None:
        return self._settings.reranker_model

    def rerank(self, payload: dict) -> dict:
        return self._transport.rerank(self.url, payload)

    def command(self) -> list[str]:
        return [self._settings.llama_server, "--reranking", "-m", str(self._settings.reranker_model),
                "--pooling", self._settings.reranker_pooling,
                "--port", str(LLAMA_SERVER_PORT), "--host", LLAMA_SERVER_HOST]

    def start(self) -> None:
        if self._process is not None or self._transport.healthy(self.url):
            return
        process = self._started()
        try:
            self._await_health(process)
        except RerankerUnavailable:
            self._terminate(process)
            raise
        self._process = process

    def stop(self) -> None:
        process, self._process = self._process, None
        if process is not None:
            self._terminate(process)

    @property
    def _binary(self) -> str:
        return self._settings.llama_server

    def _started(self) -> subprocess.Popen:
        try:
            return self._control.launch(self.command())
        except OSError as error:
            raise RerankerUnavailable(f"could not start {self._binary}: {error}") from error

    def _await_health(self, process: subprocess.Popen) -> None:
        starting = _StartingProcess(process)
        deadline = self._control.now() + HEALTH_TIMEOUT_SECONDS
        while not self._transport.healthy(self.url):
            self._require_still_starting(starting, deadline)
            self._control.sleep(HEALTH_POLL_SECONDS)

    def _require_still_starting(self, starting: _StartingProcess, deadline: float) -> None:
        if starting.exited():
            raise RerankerUnavailable(f"{self._binary} {starting.exit_report()}")
        if self._control.now() > deadline:
            raise RerankerUnavailable(f"{self._binary} not healthy after {HEALTH_TIMEOUT_SECONDS} s")

    @staticmethod
    def _terminate(process: subprocess.Popen) -> None:
        process.terminate()
        try:
            process.wait(timeout=STOP_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()


class PerQueryLifetime:
    @contextmanager
    def serving(self, server: LlamaServerProcess) -> Iterator[None]:
        server.start()
        try:
            yield
        finally:
            server.stop()


class ProcessLifetime:
    @contextmanager
    def serving(self, server: LlamaServerProcess) -> Iterator[None]:
        server.start()
        yield


class ProbeVerdict:
    def __init__(self, matching: float, unrelated: float) -> None:
        self._matching = matching
        self._unrelated = unrelated

    def failure(self) -> str | None:
        if self._is_degenerate():
            return f"degenerate scores {self._scores()}"
        if self._unrelated >= self._matching:
            return f"wrong order {self._scores()}"
        return None

    def _is_degenerate(self) -> bool:
        largest = max(abs(self._matching), abs(self._unrelated))
        return largest < DEGENERATE_SCORE_MAGNITUDE or self._matching == self._unrelated

    def _scores(self) -> str:
        return f"(matching {self._matching!r}, unrelated {self._unrelated!r})"


class ProbeLedger:
    def __init__(self) -> None:
        self._failures: dict[Path, str | None] = {}

    def probed(self, model: Path) -> bool:
        return model in self._failures

    def failure(self, model: Path) -> str | None:
        return self._failures[model]

    def record(self, model: Path, failure: str | None) -> None:
        self._failures[model] = failure


PROBES_THIS_SESSION = ProbeLedger()


class LlamaReranker:
    def __init__(self, server: LlamaServerProcess | None = None, ledger: ProbeLedger | None = None,
                 lifetime: PerQueryLifetime | ProcessLifetime | None = None) -> None:
        self._server = server or LlamaServerProcess.on_this_machine()
        self._ledger = ledger or PROBES_THIS_SESSION
        self._lifetime = lifetime or PerQueryLifetime()

    def unavailable_cause(self) -> str | None:
        model = self._server.model
        if model is None:
            return f"machine.json names no {RERANKER_MODEL_KEY}"
        if not model.is_file():
            return f"{RERANKER_MODEL_KEY} {model} is not a file"
        return self.probe_failure()

    def probe_failure(self) -> str | None:
        model = self._server.model
        if model is None or not self._ledger.probed(model):
            return None
        return self._ledger.failure(model)

    def scores(self, query: str, passages: list[str]) -> list[float]:
        cause = self.unavailable_cause()
        if cause is not None:
            raise RerankerUnavailable(cause)
        with self._lifetime.serving(self._server):
            self._require_sane_probe()
            return self._scored(query, passages)

    def stop(self) -> None:
        self._server.stop()

    def _require_sane_probe(self) -> None:
        model = self._server.model
        if not self._ledger.probed(model):
            self._ledger.record(model, self._run_probe())
        failure = self._ledger.failure(model)
        if failure is not None:
            raise RerankerUnavailable(failure)

    def _run_probe(self) -> str | None:
        model = self._server.model
        try:
            matching, unrelated = self._scored(PROBE_QUERY, [PROBE_MATCHING_PASSAGE, PROBE_UNRELATED_PASSAGE])
        except RerankerUnavailable as error:
            return f"{PROBE_FAILED}: {error}"
        verdict = ProbeVerdict(matching, unrelated).failure()
        return None if verdict is None else f"{PROBE_FAILED} with {verdict}: {model.name} is not scoring sanely"

    def _scored(self, query: str, passages: list[str]) -> list[float]:
        return self._parsed(self._server.rerank(self._payload(query, passages)), len(passages))

    @staticmethod
    def _payload(query: str, passages: list[str]) -> dict:
        return {"model": RERANK_MODEL_NAME, "query": query, "documents": passages}

    @staticmethod
    def _parsed(response: dict, expected: int) -> list[float]:
        try:
            return _scores_by_index(response["results"], expected)
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise RerankerUnavailable(f"malformed rerank response: {type(error).__name__}: {error}") from error


def _scores_by_index(results: list[dict], expected: int) -> list[float]:
    scores = [0.0] * expected
    for result in results:
        scores[result["index"]] = float(result["relevance_score"])
    return scores
