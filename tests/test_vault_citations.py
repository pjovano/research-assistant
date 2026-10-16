from __future__ import annotations

import unittest

from _support import LiveTree

LiveTree.activate()

import vault

HELD = "Hegel - 1969 - Wissenschaft der Logik"

class TestControlledVocabularies(unittest.TestCase):
    def test_the_five_source_types_are_defined(self) -> None:
        self.assertEqual({"article", "monograph", "historical", "textbook", "transcript"},
                         set(vault.SOURCE_TYPES))

    def test_the_three_source_roles_are_defined(self) -> None:
        self.assertEqual({"primary", "secondary", "reference"}, set(vault.SOURCE_ROLES))

    def test_every_source_type_has_a_description(self) -> None:
        undescribed = [name for name, text in vault.SOURCE_TYPES.items() if not text.strip()]
        self.assertEqual([], undescribed)

    def test_every_source_role_has_a_description(self) -> None:
        undescribed = [name for name, text in vault.SOURCE_ROLES.items() if not text.strip()]
        self.assertEqual([], undescribed)


class TestCommentaryTarget(unittest.TestCase):
    def test_a_wikilinked_target_is_unwrapped(self) -> None:
        self.assertEqual(HELD, vault.commentary_target({"commentary_on": f"[[{HELD}]]"}))

    def test_an_absent_target_reads_as_none(self) -> None:
        self.assertIsNone(vault.commentary_target({}))


class TestWikilinkTarget(unittest.TestCase):
    def test_a_heading_anchor_is_not_part_of_the_target(self) -> None:
        self.assertEqual("Being", vault.wikilink_target("[[Being#One|shown]]"))

    def test_an_aliased_link_yields_its_target(self) -> None:
        self.assertEqual("Being", vault.wikilink_target("[[Being|the topic]]"))


class TestFieldTopics(unittest.TestCase):
    def test_wikilinked_topics_are_unwrapped(self) -> None:
        self.assertEqual(["Being", "Logic"], vault.field_topics({"field": ["[[Being]]", "[[Logic]]"]}))

    def test_bare_topic_names_pass_through(self) -> None:
        self.assertEqual(["Being"], vault.field_topics({"field": ["Being"]}))

    def test_an_absent_field_yields_no_topics(self) -> None:
        self.assertEqual([], vault.field_topics({}))


class TestCitekeyYear(unittest.TestCase):
    def test_the_original_year_outranks_the_edition_year(self) -> None:
        self.assertEqual("1807", vault.citekey_year({"orig_year": 1807, "year": 1969}))

    def test_the_edition_year_is_used_when_there_is_no_original(self) -> None:
        self.assertEqual("1969", vault.citekey_year({"year": 1969}))

    def test_a_yearless_record_is_undated(self) -> None:
        self.assertEqual("n.d.", vault.citekey_year({}))


class TestUniqueCitekey(unittest.TestCase):
    def test_an_unclaimed_key_is_returned_unchanged(self) -> None:
        self.assertEqual("harris1997", vault.unique_citekey("harris1997", set()))

    def test_a_collision_takes_the_next_letter(self) -> None:
        self.assertEqual("harris1997a", vault.unique_citekey("harris1997", {"harris1997"}))

    def test_successive_collisions_walk_the_alphabet(self) -> None:
        taken = {"harris1997", "harris1997a"}
        self.assertEqual("harris1997b", vault.unique_citekey("harris1997", taken))

    def test_exhausting_the_alphabet_raises(self) -> None:
        taken = {"x2000"} | {f"x2000{c}" for c in "abcdefghijklmnopqrstuvwxyz"}
        with self.assertRaises(ValueError):
            vault.unique_citekey("x2000", taken)


if __name__ == "__main__":
    unittest.main()
