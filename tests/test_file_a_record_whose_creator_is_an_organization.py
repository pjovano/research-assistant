from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

from _file.preview import FilingPreview
from _file_fixtures import INBOX_PDF_NAME, VaultTestCase

ORGANIZATION = "Royal Society"
ORGANIZATION_CARD = ("---\nzotero:\n  title: A Work\n  date: '2020'\n  creators:\n"
                     f"  - creatorType: author\n    name: {ORGANIZATION}\n---\n")
ORGANIZATION_AND_PERSON_CARD = ("---\nzotero:\n  title: A Work\n  date: '2020'\n  creators:\n"
                                f"  - creatorType: author\n    name: {ORGANIZATION}\n"
                                "  - creatorType: author\n    firstName: Jane\n    lastName: Doe\n---\n")


class TestARecordWhoseOnlyCreatorIsAnOrganization(VaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.preview = self.preview_of(ORGANIZATION_CARD)

    def preview_of(self, card: str) -> FilingPreview:
        path = self.pdf(INBOX_PDF_NAME).write()
        self.draft_card(card)
        return FilingPreview.of(path)

    def test_the_organization_is_the_first_creator_of_the_filename(self) -> None:
        self.assertEqual(f"{ORGANIZATION} - 2020 - A Work.pdf", self.preview.library_filename())

    def test_the_organization_is_kept_whole_as_a_creator(self) -> None:
        self.assertEqual([{"firstName": "", "lastName": ORGANIZATION}], self.preview.meta["authors"])


class TestARecordNamingAnOrganizationBeforeAPerson(TestARecordWhoseOnlyCreatorIsAnOrganization):
    def setUp(self) -> None:
        VaultTestCase.setUp(self)
        self.preview = self.preview_of(ORGANIZATION_AND_PERSON_CARD)

    def test_the_organization_is_the_first_creator_of_the_filename(self) -> None:
        self.assertEqual(f"{ORGANIZATION} and Doe - 2020 - A Work.pdf", self.preview.library_filename())

    def test_the_organization_is_kept_whole_as_a_creator(self) -> None:
        self.assertEqual([ORGANIZATION, "Doe"], [author["lastName"] for author in self.preview.meta["authors"]])


if __name__ == "__main__":
    unittest.main()
