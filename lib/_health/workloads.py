from __future__ import annotations

from pathlib import Path

from _health.readings import OTHER_PREFIX
from server_command_line import ServerCommandLine

MODEL_SERVER_LABEL = "model-server"
EXTRACT_LABEL = "extract"
SCRIPT_LABELS = {"extract.py": EXTRACT_LABEL, "transcribe.py": "transcribe"}
PROGRAM_LABELS = {"ollama": "ollama", "llama-server": "llama-server", "whisper-cli": "whisper"}
SERVER_SCRIPT_LABELS = {("search", "server.py"): "vault-rag"}


class WorkloadLabels:
    def __init__(self, model_servers: ServerCommandLine | None = None) -> None:
        self._model_servers = model_servers or ServerCommandLine()

    def label(self, arguments: list[str], name: str) -> str:
        if self._model_servers.matches(arguments):
            return MODEL_SERVER_LABEL
        return self._named_label(arguments) or f"{OTHER_PREFIX}{name}"

    def _named_label(self, arguments: list[str]) -> str | None:
        paths = [Path(argument) for argument in arguments]
        program = PROGRAM_LABELS.get(paths[0].name) if paths else None
        scripts = (self._script_label(path) for path in paths[1:])
        return program or next((label for label in scripts if label), None)

    @staticmethod
    def _script_label(path: Path) -> str | None:
        return SCRIPT_LABELS.get(path.name) or SERVER_SCRIPT_LABELS.get((path.parent.name, path.name))
