from __future__ import annotations

import os
from collections.abc import Mapping

import vault
from _ports.host import SyncedFolder
from _vault.machine import MachineConfigError, load_machine_config
from providers import ProviderNotConfigured, Providers


class SyncedFolderUnavailable(LookupError):
    pass


class ConfiguredSyncedFolder:
    def __init__(self, machine: dict, environ: Mapping[str, str]) -> None:
        self._machine = machine
        self._environ = environ

    @classmethod
    def of_machine(cls) -> ConfiguredSyncedFolder:
        return cls(load_machine_config(), os.environ)

    def built(self) -> SyncedFolder:
        try:
            adapter = Providers.from_machine(self._machine, self._environ).sync()
        except (ProviderNotConfigured, MachineConfigError) as unconfigured:
            raise SyncedFolderUnavailable(f"the synced folder cannot be checked for conflict copies or for files "
                                          f"whose bytes are not on disk: {unconfigured}") from unconfigured
        return adapter(vault.CORPUS_DIR)
