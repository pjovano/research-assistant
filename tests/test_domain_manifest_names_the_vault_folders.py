from __future__ import annotations

import json
import unittest

from _domain_settings import DOMAIN_MANIFEST, DocumentsFolders, GeneratedSettings
from _support import LiveTree

LiveTree.activate()

from _vault import paths

WRITE_ACCESS = "write"


class TheManifestThePathsAndTheSandboxNameTheSameFolders(unittest.TestCase):
    def setUp(self) -> None:
        manifest = json.loads(DOMAIN_MANIFEST.read_text(encoding="utf-8"))
        self.manifest_folders = {folder["name"] for folder in manifest["folders"]
                                 if folder["access"] == WRITE_ACCESS}

    def test_the_manifest_lists_every_folder_the_vault_paths_name(self) -> None:
        path_folders = {directory.relative_to(paths.VAULT_ROOT).parts[0]
                        for directory in (paths.LIBRARY_DIR, paths.OBSIDIAN_VAULT_DIR)}
        self.assertEqual(path_folders, self.manifest_folders)

    def test_the_generated_sandbox_writes_in_exactly_the_manifest_folders(self) -> None:
        allowed = GeneratedSettings.blocks()["sandbox"]["filesystem"]["allowWrite"]
        self.assertEqual(self.manifest_folders, DocumentsFolders(allowed).names())


if __name__ == "__main__":
    unittest.main()
