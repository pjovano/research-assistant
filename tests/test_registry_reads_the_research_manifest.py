from __future__ import annotations

import json
import unittest

from _domain_settings import DOMAIN_MANIFEST, DomainCommand
from _support import LiveTree

LiveTree.activate()

from _vault import paths

UNATTENDED_WRITERS = ("take-notes", "ingest")
WRITE_LEVEL = "write"
READ_ONLY_LEVEL = "read-only"
REQUEST_KINDS = {"research questions", "discover", "notes", "drafts", "projects", "ingest"}


class TheRegistryValidatesTheResearchManifest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = DomainCommand("registry", DOMAIN_MANIFEST).output()
        cls.domain = cls.registry["domains"][0]
        cls.levels = {skill["name"]: skill["unattended"] for skill in cls.domain["entry_skills"]}

    def test_it_lists_the_research_domain_and_refuses_nothing(self) -> None:
        self.assertEqual((["research-assistant"], []), ([domain["name"] for domain in self.registry["domains"]],
                                                         self.registry["refused"]))

    def test_the_domain_handles_each_kind_of_research_request(self) -> None:
        self.assertEqual(REQUEST_KINDS, {handle["kind"] for handle in self.domain["handles"]})

    def test_take_notes_writes_unattended(self) -> None:
        self.assertEqual(WRITE_LEVEL, self.levels["take-notes"])

    def test_ingest_runs_unattended_at_a_level_other_than_read_only(self) -> None:
        self.assertNotEqual(READ_ONLY_LEVEL, self.levels["ingest"])

    def test_every_other_entry_skill_is_read_only_unattended(self) -> None:
        others = {skill: level for skill, level in self.levels.items() if skill not in UNATTENDED_WRITERS}
        self.assertEqual({READ_ONLY_LEVEL}, set(others.values()))

    def test_every_entry_skill_with_the_web_capability_declares_untrusted_content(self) -> None:
        web_skills = [skill for skill in self.domain["entry_skills"] if "web" in skill["capabilities"]]
        self.assertTrue(web_skills and all("untrusted_content" in skill["exposure"] for skill in web_skills))


class TheManifestNamesTheObsidianVault(unittest.TestCase):
    def test_the_vault_is_the_folder_the_vault_paths_name_as_the_obsidian_vault(self) -> None:
        manifest = json.loads(DOMAIN_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(paths.OBSIDIAN_VAULT_DIR.relative_to(paths.VAULT_ROOT).parts[0], manifest["vault"])


if __name__ == "__main__":
    unittest.main()
