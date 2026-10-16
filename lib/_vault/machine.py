from __future__ import annotations

import json
from pathlib import Path

MACHINE_CONFIG_PATH = Path.home() / ".research-vault" / "machine.json"
PROFILE_KEY = "profile"
PROVIDERS_KEY = "providers"
DEFAULT_PROFILE = "mac-local"
PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"
PROFILE_SUFFIX = ".json"
_ENCODING = "utf-8"


class MachineConfigError(ValueError):
    pass


class UnknownProfile(MachineConfigError):
    pass


class MalformedProviders(MachineConfigError):
    pass


class MachineConfig:
    def __init__(self, path: Path) -> None:
        self._path = path

    def loaded(self) -> dict:
        try:
            text = self._path.read_text(encoding=_ENCODING)
        except OSError:
            return {}
        return self._parsed(text)

    def _parsed(self, text: str) -> dict:
        try:
            return json.loads(text) or {}
        except ValueError as error:
            raise SystemExit(f"{self._path} is not valid JSON: {error}") from error


class ProviderChoices:
    def __init__(self, machine: dict, source: Path = MACHINE_CONFIG_PATH, profiles_dir: Path = PROFILES_DIR) -> None:
        self._machine = machine
        self._source = source
        self._profiles_dir = profiles_dir

    @property
    def profile(self) -> str:
        return str(self._machine.get(PROFILE_KEY) or DEFAULT_PROFILE)

    def entries(self) -> dict[str, dict]:
        return {**self._profile_entries(), **self._overrides()}

    def _overrides(self) -> dict[str, dict]:
        overrides = self._machine.get(PROVIDERS_KEY) or {}
        if not isinstance(overrides, dict):
            raise MalformedProviders(f"{self._source}'s {PROVIDERS_KEY} must be an object of provider entries, "
                                 f"not {type(overrides).__name__}")
        return overrides

    def _profile_entries(self) -> dict[str, dict]:
        if self.profile not in self.available():
            raise UnknownProfile(f"{self._source} names the profile {self.profile!r} under {PROFILE_KEY}; "
                                 f"the profiles are {', '.join(self.available())}")
        path = self._profiles_dir / f"{self.profile}{PROFILE_SUFFIX}"
        return json.loads(path.read_text(encoding=_ENCODING))[PROVIDERS_KEY]

    def available(self) -> list[str]:
        return sorted(path.stem for path in self._profiles_dir.glob(f"*{PROFILE_SUFFIX}"))


def load_machine_config() -> dict:
    return MachineConfig(MACHINE_CONFIG_PATH).loaded()
