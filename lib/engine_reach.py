from __future__ import annotations

import sys
from collections.abc import Callable

from engine_environment import EngineEnvironment

MACOS = "darwin"
OPENAI_PATH = "/v1"
NO_METAL = ("this process has no Metal, as a command run inside the sandbox has none, so the engine's model "
            "servers fail every request: run the command outside the sandbox, in the form the ingest skill states")


class EngineUnreachable(RuntimeError):
    pass


class MetalAccess:
    def __init__(self, platform: str = sys.platform, metal_available: Callable[[], bool] | None = None) -> None:
        self._platform = platform
        self._metal_available = metal_available or self._torch_sees_metal

    def failure(self) -> str | None:
        if self._platform != MACOS or self._metal_available():
            return None
        return NO_METAL

    @staticmethod
    def _torch_sees_metal() -> bool:
        import torch
        return torch.backends.mps.is_available()


class ServerReach:
    def __init__(self, manager_factory: Callable | None = None, healthy: Callable[[str], bool] | None = None) -> None:
        self._manager_factory = manager_factory or self._surya_manager
        self._healthy = healthy or self._surya_health

    def failure(self) -> str | None:
        manager = self._manager_factory()
        try:
            manager.start()
        except Exception as error:
            return f"the engine's model server did not start: {type(error).__name__}: {error}"
        server_url = self._server_url(manager)
        return None if self._healthy(server_url) else f"the engine's model server does not answer at {server_url}"

    @staticmethod
    def _server_url(manager) -> str:
        return manager.backend.handle.base_url.removesuffix(OPENAI_PATH)

    @staticmethod
    def _surya_manager():
        EngineEnvironment().apply()
        from surya.inference import SuryaInferenceManager
        return SuryaInferenceManager()

    @staticmethod
    def _surya_health(server_url: str) -> bool:
        from surya.inference.backends.spawn import probe_health
        return probe_health(server_url)


class EngineReach:
    def __init__(self, checks: tuple | None = None) -> None:
        self._checks = checks or (MetalAccess(), ServerReach())

    def require(self) -> None:
        for check in self._checks:
            failure = check.failure()
            if failure is not None:
                raise EngineUnreachable(failure)
