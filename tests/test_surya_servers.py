from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from _support import LiveTree

LiveTree.activate()

import surya_servers
import vault

SLEEPING_CHILD = [sys.executable, "-c", "import time; time.sleep(30)"]
EXITING_CHILD = [sys.executable, "-c", "pass"]
REAPER_COMMAND = ["reap"]
FAKE_PID = 424242
CHILD_WAIT_SECONDS = 10
LAYOUT_SERVER = [sys.executable, "-m", "surya.fast_layout.server", "--host", "127.0.0.1", "--port", "59145"]
RELAUNCHED_INTERPRETER = "/Library/Frameworks/Python.framework/Versions/3.12/Resources/Python.app/Contents/MacOS/Python"
OCR_ERROR_SERVER = [sys.executable, "-m", "surya.ocr_error.server", "--port", "62494"]
SLEEPING_MODULE_NAME = "sleeping_test_server"
SLEEPING_MODULE_SOURCE = "import time\ntime.sleep(30)\n"
SCAN_WAIT_SECONDS = 5.0
POLL_SECONDS = 0.05
OCR_MODEL = "test-org/test-ocr-model"
OTHER_MODEL = "test-org/test-other-model"
LLAMA_SERVER_PATH = "bin/llama-server"
OCR_LLAMA_SERVER = [LLAMA_SERVER_PATH, "-m", "ocr.gguf", "--port", "60608", "--alias", OCR_MODEL, "--jinja"]
RERANKING_LLAMA_SERVER = [LLAMA_SERVER_PATH, "--reranking", "-m", "reranker.gguf", "--port", "8012"]
REPLACED_OCR_SERVER = ["llama-server", "-c", "import time; time.sleep(30)", "--alias", OCR_MODEL]


class FakeServerProcesses:
    def __init__(self, pids: list[int] | None = None) -> None:
        self._pids = pids or []

    def pids(self) -> list[int]:
        return list(self._pids)


class FakeLauncher:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def launch(self, command: list[str]) -> types.SimpleNamespace:
        self.commands.append(command)
        return types.SimpleNamespace(pid=FAKE_PID)


class ChildProcessTestCase(unittest.TestCase):
    def sleeping_child(self) -> subprocess.Popen:
        child = subprocess.Popen(SLEEPING_CHILD)
        self.addCleanup(self._discard, child)
        return child

    @staticmethod
    def exited_pid() -> int:
        child = subprocess.Popen(EXITING_CHILD)
        child.wait(timeout=CHILD_WAIT_SECONDS)
        return child.pid

    def sleeping_module_child(self) -> subprocess.Popen:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        (Path(directory.name) / f"{SLEEPING_MODULE_NAME}.py").write_text(SLEEPING_MODULE_SOURCE, encoding="utf-8")
        child = subprocess.Popen([sys.executable, "-m", SLEEPING_MODULE_NAME], cwd=directory.name)
        self.addCleanup(self._discard, child)
        return child

    @staticmethod
    def _discard(child: subprocess.Popen) -> None:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=CHILD_WAIT_SECONDS)


class TestSuryaCacheDir(unittest.TestCase):
    def test_a_machine_naming_no_key_uses_the_datalab_cache_under_home(self) -> None:
        self.assertEqual(Path.home() / ".cache" / "datalab" / "surya", surya_servers.surya_cache_dir({}))

    def test_a_configured_path_is_expanded_under_home(self) -> None:
        configured = surya_servers.surya_cache_dir({"surya_cache_dir": "~/caches/surya"})
        self.assertEqual(Path.home() / "caches" / "surya", configured)

    def test_the_sentinel_directory_is_the_cache_the_vault_machine_config_names(self) -> None:
        self.assertEqual(surya_servers.surya_cache_dir(vault.MACHINE), surya_servers.SENTINEL_DIR)


class TestProcess(ChildProcessTestCase):
    def test_this_process_is_alive(self) -> None:
        self.assertTrue(surya_servers.Process(os.getpid()).alive())

    def test_an_exited_process_is_not_alive(self) -> None:
        self.assertFalse(surya_servers.Process(self.exited_pid()).alive())

    def test_an_exited_process_its_parent_has_not_reaped_is_not_alive(self) -> None:
        child = subprocess.Popen(EXITING_CHILD)
        self.addCleanup(child.wait, CHILD_WAIT_SECONDS)
        self.assertFalse(self._alive_once_exited(child.pid))

    def test_terminating_a_child_ends_it_with_sigterm(self) -> None:
        child = self.sleeping_child()
        surya_servers.Process(child.pid).terminate()
        self.assertEqual(-signal.SIGTERM, child.wait(timeout=CHILD_WAIT_SECONDS))

    def test_terminating_an_exited_process_raises_nothing(self) -> None:
        surya_servers.Process(self.exited_pid()).terminate()
        self.assertFalse(surya_servers.Process(self.exited_pid()).alive())


    @staticmethod
    def _alive_once_exited(pid: int) -> bool:
        deadline = time.monotonic() + CHILD_WAIT_SECONDS
        while surya_servers.Process(pid).alive() and time.monotonic() < deadline:
            time.sleep(POLL_SECONDS)
        return surya_servers.Process(pid).alive()


class TestReaperProcess(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.pid_file = Path(directory.name) / "engine-reaper.json"
        self.launcher = FakeLauncher()
        self.reaper = surya_servers.ReaperProcess(self.pid_file, self.launcher)

    def test_a_reaper_no_file_names_is_launched_and_its_pid_recorded(self) -> None:
        self.reaper.ensure_running(REAPER_COMMAND)
        recorded = surya_servers.PidFile(self.pid_file).pid()
        self.assertEqual(([REAPER_COMMAND], FAKE_PID), (self.launcher.commands, recorded))

    def test_a_reaper_the_file_names_alive_is_not_launched_again(self) -> None:
        surya_servers.PidFile(self.pid_file).write(os.getpid())
        self.reaper.ensure_running(REAPER_COMMAND)
        self.assertEqual([], self.launcher.commands)

    def test_a_reaper_the_file_names_dead_is_replaced(self) -> None:
        surya_servers.PidFile(self.pid_file).write(ChildProcessTestCase.exited_pid())
        self.reaper.ensure_running(REAPER_COMMAND)
        self.assertEqual(FAKE_PID, surya_servers.PidFile(self.pid_file).pid())


class TestServerCommandLine(unittest.TestCase):
    def setUp(self) -> None:
        self.command_line = surya_servers.ServerCommandLine()

    def test_the_layout_server_the_vault_interpreter_runs_is_a_server(self) -> None:
        self.assertTrue(self.command_line.matches(LAYOUT_SERVER))

    def test_the_ocr_error_server_the_vault_interpreter_runs_is_a_server(self) -> None:
        self.assertTrue(self.command_line.matches(OCR_ERROR_SERVER))

    def test_a_surya_server_an_interpreter_that_relaunched_itself_runs_is_a_server(self) -> None:
        self.assertTrue(self.command_line.matches([RELAUNCHED_INTERPRETER, *LAYOUT_SERVER[1:]]))

    def test_a_surya_module_that_is_not_a_server_is_not_a_server(self) -> None:
        self.assertFalse(self.command_line.matches([sys.executable, "-m", "surya.scripts.ocr_text"]))

    def test_a_command_line_without_a_module_is_not_a_server(self) -> None:
        self.assertFalse(self.command_line.matches([sys.executable]))

    def test_a_llama_server_serving_a_model_a_server_record_names_is_a_server(self) -> None:
        command_line = surya_servers.ServerCommandLine(frozenset({OCR_MODEL}))
        self.assertTrue(command_line.matches(OCR_LLAMA_SERVER))

    def test_a_llama_server_serving_a_model_no_server_record_names_is_not_a_server(self) -> None:
        command_line = surya_servers.ServerCommandLine(frozenset({OTHER_MODEL}))
        self.assertFalse(command_line.matches(OCR_LLAMA_SERVER))

    def test_a_llama_server_started_without_an_alias_is_not_a_server(self) -> None:
        command_line = surya_servers.ServerCommandLine(frozenset({OCR_MODEL}))
        self.assertFalse(command_line.matches(RERANKING_LLAMA_SERVER))


class ServerRecordDirectory:
    def __init__(self, test: unittest.TestCase) -> None:
        directory = tempfile.TemporaryDirectory()
        test.addCleanup(directory.cleanup)
        self._path = Path(directory.name)
        patcher = patch.object(surya_servers, "SENTINEL_DIR", self._path)
        patcher.start()
        test.addCleanup(patcher.stop)

    def record(self, name: str, fields: dict) -> Path:
        path = self._path / f"{name}{surya_servers.SENTINEL_SUFFIX}"
        path.write_text(json.dumps(fields), encoding="utf-8")
        return path


class TestServerRecords(unittest.TestCase):
    def test_the_models_are_those_the_server_records_name(self) -> None:
        records = ServerRecordDirectory(self)
        records.record("llamacpp", {"pid": FAKE_PID, "model": OCR_MODEL})
        records.record("layout", {"pid": FAKE_PID})
        self.assertEqual(frozenset({OCR_MODEL}), surya_servers.ServerRecords().models())


class TestServerProcesses(ChildProcessTestCase):
    def test_a_running_process_whose_command_line_matches_is_found(self) -> None:
        child = self.sleeping_module_child()
        command_line = surya_servers.ServerCommandLine(module=re.compile(re.escape(SLEEPING_MODULE_NAME)))
        self.assertIn(child.pid, self._found_pids(surya_servers.ServerProcesses(command_line), child.pid))

    def test_a_running_process_whose_command_line_does_not_match_is_not_found(self) -> None:
        child = self.sleeping_child()
        self.assertNotIn(child.pid, surya_servers.ServerProcesses().pids())

    def test_an_ocr_server_whose_record_a_newer_server_replaced_is_found(self) -> None:
        ServerRecordDirectory(self).record("llamacpp", {"pid": FAKE_PID, "model": OCR_MODEL})
        child = self.replaced_ocr_server()
        self.assertIn(child.pid, self._found_pids(surya_servers.ServerProcesses(), child.pid))

    def replaced_ocr_server(self) -> subprocess.Popen:
        child = subprocess.Popen(REPLACED_OCR_SERVER, executable=sys.executable)
        self.addCleanup(self._discard, child)
        return child

    @staticmethod
    def _found_pids(processes: surya_servers.ServerProcesses, awaited_pid: int) -> list[int]:
        deadline = time.monotonic() + SCAN_WAIT_SECONDS
        pids = processes.pids()
        while awaited_pid not in pids and time.monotonic() < deadline:
            time.sleep(POLL_SECONDS)
            pids = processes.pids()
        return pids


class TestStopAll(ChildProcessTestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.sentinels = Path(directory.name)
        patcher = patch.object(surya_servers, "SENTINEL_DIR", self.sentinels)
        patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def stopped_by(servers: surya_servers.SuryaServers) -> list[int]:
        servers.stop_all()
        return servers.stopped_pids

    def sentinel(self, name: str, pid: int) -> Path:
        path = self.sentinels / f"{name}{surya_servers.SENTINEL_SUFFIX}"
        path.write_text(json.dumps({"pid": pid}), encoding="utf-8")
        return path

    def test_a_live_server_is_stopped_and_its_sentinel_removed(self) -> None:
        child = self.sleeping_child()
        sentinel = self.sentinel("layout", child.pid)
        stopped = self.stopped_by(self.servers())
        self.assertEqual(([child.pid], False, -signal.SIGTERM),
                         (stopped, sentinel.exists(), child.wait(timeout=CHILD_WAIT_SECONDS)))

    def test_a_sentinel_naming_a_dead_server_is_removed_and_not_counted(self) -> None:
        sentinel = self.sentinel("layout", self.exited_pid())
        self.assertEqual(([], False), (self.stopped_by(self.servers()), sentinel.exists()))

    def test_a_live_server_no_sentinel_names_is_stopped(self) -> None:
        child = self.sleeping_child()
        stopped = self.stopped_by(self.servers([child.pid]))
        self.assertEqual(([child.pid], -signal.SIGTERM), (stopped, child.wait(timeout=CHILD_WAIT_SECONDS)))

    def test_a_server_both_a_sentinel_and_the_scan_name_is_stopped_once(self) -> None:
        child = self.sleeping_child()
        self.sentinel("layout", child.pid)
        self.assertEqual([child.pid], self.stopped_by(self.servers([child.pid])))

    def test_servers_run_while_a_live_server_no_sentinel_names_remains(self) -> None:
        self.assertTrue(self.servers([self.sleeping_child().pid]).running())

    def test_servers_do_not_run_with_no_sentinel_and_no_server_process(self) -> None:
        self.assertFalse(self.servers().running())

    @staticmethod
    def servers(scanned_pids: list[int] | None = None) -> surya_servers.SuryaServers:
        return surya_servers.SuryaServers(FakeServerProcesses(scanned_pids))


if __name__ == "__main__":
    unittest.main()
