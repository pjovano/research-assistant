from __future__ import annotations

import contextlib
import io
import json
import unittest
from unittest import mock

from _writing_fixtures import IDEA, OTHER_IDEA, PAPER, WritingTestCase

import vault
from _writing.atomic_note import AtomicNote
from _writing.board import Board
from _writing.board_cards import ArrowFactory, CardFace, CardFactory, Point, RelationStyle
from _writing.board_file import BoardFile, BoardState
from _writing.board_sync import AnswerArrow, Beside, BoardReading, BoardSync, CardAddition, CardMove, CardText, NotePlacement
from _writing.cli import CommandLine
from _writing.lzstring import decompress_from_base64
from _writing.project_file import ABSTRACT, CHANGE_LOG, DRAFTS, PROJECT, QUESTION, ProjectFile
from _writing.saved import BoardBackups, save_text
from _writing.placement import HeadingLine

COMPRESSED = ("N4IgLgngDgpiBcACEMAeBjAhgGwJYBMAnTAdxABpkZsYBbGAOzAGcFEBtUAtkTAI3T4YAMwDmACwrJIsHoRjowmBqJpSQuZgBFqMMDHxth"
              "OZjEog8DANY927AJJDMAXWeJAKASJAI8CAPfESARfEBe4BAAX2cQoA")
PROJECTS_LINE = f'---\nprojects:\n- "[[{PAPER}]]"\n---\n'
OLD_PROJECT_FILE = ("---\nstatus: drafting\nparents: []\nchildren: []\n---\n\n# Abstract\n\nMeasure unites quality "
                    "and quantity.\n\n# Drafts\n\n- [[A draft - v01]]\n\n# To do\n\n# Outline\n\n# Glossary\n")


DRAWN_BY_HAND = {"id": "abcdefgh", "type": "rectangle", "x": 0, "y": 0, "width": 200, "height": 100, "isDeleted": False}
HAND_DRAWN_BOARD = ("---\nexcalidraw-plugin: parsed\ntags: [excalidraw]\n---\n\n%%\n## Drawing\n```json\n"
                    + json.dumps({"type": "excalidraw", "elements": [DRAWN_BY_HAND]}) + "\n```\n%%")


def card(title: str, at: Point = Point(0, 0)) -> list[dict]:
    return CardFactory().card(at, CardFace(title, "a claim", link=f"[[{title}]]"))


class TestCompressedDrawing(unittest.TestCase):
    def test_a_compressed_drawing_is_read_back_with_its_characters_outside_ascii(self) -> None:
        drawing = json.loads(decompress_from_base64(COMPRESSED))
        self.assertEqual("[[Idea]] — τὸ ὄν", drawing["elements"][0]["link"])

    def test_an_empty_stream_is_an_empty_text(self) -> None:
        self.assertEqual("", decompress_from_base64(""))


class TestBoardFile(unittest.TestCase):
    FRONT = "---\nstatus: planning\n---\n\n# Drafts\n\n- [[A draft - v01]]\n"

    def written(self, elements: list[dict], state: BoardState = BoardState()) -> BoardFile:
        return BoardFile(BoardFile(self.FRONT).written(elements, state))

    def test_a_text_element_ending_on_half_a_character_pair_is_written_and_read_back(self) -> None:
        halved = {"id": "abcdefgh", "type": "text", "text": "cut \ud83d", "rawText": "cut \ud83d"}
        written = BoardFile(self.FRONT).written([halved], BoardState())
        self.assertEqual("cut \ud83d", BoardFile(written.encode("utf-8").decode("utf-8")).elements()[0]["text"])

    def test_a_file_without_a_drawing_holds_no_element(self) -> None:
        self.assertEqual([], BoardFile(self.FRONT).elements())

    def test_a_compressed_drawing_is_read_through_its_line_breaks(self) -> None:
        text = f"{self.FRONT}\n# Excalidraw Data\n\n%%\n## Drawing\n```compressed-json\n{COMPRESSED[:60]}\n\n{COMPRESSED[60:]}\n```\n%%\n"
        self.assertEqual(["abcdefgh"], [element["id"] for element in BoardFile(text).elements()])

    def test_the_elements_written_are_read_back(self) -> None:
        elements = card(IDEA)
        self.assertEqual([element["id"] for element in elements],
                         [element["id"] for element in self.written(elements).elements()])

    def test_a_deleted_element_is_not_read(self) -> None:
        elements = card(IDEA)
        elements[1]["isDeleted"] = True
        self.assertEqual(len(elements) - 1, len(self.written(elements).elements()))

    def test_the_markdown_side_is_kept(self) -> None:
        self.assertEqual("# Drafts\n\n- [[A draft - v01]]", self.written(card(IDEA)).markdown_side.strip())

    def test_the_frontmatter_gains_the_keys_the_plugin_reads_and_keeps_its_own(self) -> None:
        text = BoardFile(self.FRONT).written([], BoardState())
        self.assertTrue(text.startswith("---\nstatus: planning\nexcalidraw-plugin: parsed\ntags:\n- excalidraw\n---\n"))

    def test_the_state_is_read_back_and_written_once(self) -> None:
        state = BoardState((IDEA,), ((IDEA, "extends", OTHER_IDEA),))
        twice = BoardFile(BoardFile(self.FRONT).written([], state)).written([], state)
        self.assertEqual((state, 1), (BoardFile(twice).state(), twice.count("%% board-state")))

    def test_each_text_is_listed_with_its_id_and_each_link_with_its_element(self) -> None:
        elements = card(IDEA)
        text = BoardFile(self.FRONT).written(elements, BoardState())
        self.assertIn(f"{IDEA} ^{elements[1]['id']}\n", text)
        self.assertIn(f"{elements[0]['id']}: [[{IDEA}]]\n", text)

    def test_the_first_text_stands_on_the_line_after_its_heading_so_that_it_gains_no_line_break(self) -> None:
        elements = card(IDEA)
        text = BoardFile(self.FRONT).written(elements, BoardState())
        self.assertIn(f"## Text Elements\n{IDEA} ^", text)

    def test_the_embedded_files_of_a_board_are_kept(self) -> None:
        text = BoardFile(self.FRONT).written([], BoardState()).replace(
            "%%\n## Drawing", "## Embedded Files\nabc123: [[figure.png]]\n\n%%\n## Drawing")
        self.assertIn("abc123: [[figure.png]]", BoardFile(text).written([], BoardState()))


class TestBoardTheUserDrew(unittest.TestCase):
    HAND_DRAWN = ("---\n\nexcalidraw-plugin: parsed\ntags: [excalidraw]\n\n---\n==⚠  Switch to EXCALIDRAW VIEW in the MORE "
                  f"OPTIONS menu of this document. ⚠==\n\n\n## Drawing\n```compressed-json\n{COMPRESSED}\n```\n%%")

    def test_a_drawing_under_no_data_heading_is_read(self) -> None:
        self.assertEqual(["abcdefgh"], [element["id"] for element in BoardFile(self.HAND_DRAWN).elements()])

    def test_the_drawing_is_kept_when_the_board_is_written_anew(self) -> None:
        board = BoardFile(self.HAND_DRAWN)
        self.assertEqual(["abcdefgh"],
                         [element["id"] for element in BoardFile(board.written(board.elements(), board.state())).elements()])

    def test_a_comment_mark_that_opens_the_drawing_is_no_part_of_the_markdown_side(self) -> None:
        self.assertEqual("", BoardFile(self.HAND_DRAWN.replace("## Drawing", "%%\n## Drawing")).markdown_side)

    def test_the_plugins_warning_line_is_no_part_of_the_markdown_side(self) -> None:
        self.assertEqual("", BoardFile(self.HAND_DRAWN).markdown_side)


class TestCards(unittest.TestCase):
    def frame(self, state: str) -> dict:
        return CardFactory().card(Point(0, 0), CardFace(IDEA, "a claim", "3 references", state, f"[[{IDEA}]]"))[0]

    def test_a_card_is_a_linked_frame_grouped_with_its_title_claim_and_footer(self) -> None:
        frame, *texts = CardFactory().card(Point(0, 0), CardFace(IDEA, "a claim", "3 references", link=f"[[{IDEA}]]"))
        self.assertEqual((f"[[{IDEA}]]", [IDEA, "a claim", "3 references"], True),
                         (frame["link"], [text["text"] for text in texts],
                          all(text["groupIds"] == frame["groupIds"] for text in texts)))

    def test_a_card_awaiting_review_is_drawn_dashed(self) -> None:
        self.assertEqual("dashed", self.frame("review")["strokeStyle"])

    def test_a_settled_card_is_drawn_solid(self) -> None:
        self.assertEqual("solid", self.frame("settled")["strokeStyle"])

    def test_the_frame_reaches_beneath_its_last_line(self) -> None:
        frame, *texts = CardFactory().card(Point(0, 0), CardFace(IDEA, "a claim " * 30, "3 references"))
        self.assertGreater(frame["height"], max(text["y"] + text["height"] for text in texts))

    def arrow(self, kind: str) -> tuple[dict, dict, dict, dict]:
        source, target = card(IDEA)[0], card(OTHER_IDEA, Point(0, 600))[0]
        line, label = ArrowFactory().arrow(source, target, RelationStyle(kind, proposed=True))
        return source, target, line, label

    def test_an_arrow_of_a_reason_runs_from_the_note_that_gives_it_and_carries_its_relation_as_its_label(self) -> None:
        source, target, line, label = self.arrow("supports")
        self.assertEqual((source["id"], target["id"], "supports", "dashed"),
                         (line["startBinding"]["elementId"], line["endBinding"]["elementId"], label["text"],
                          line["strokeStyle"]))

    def test_an_arrow_of_an_extension_runs_from_the_note_extended_to_the_note_that_extends_it(self) -> None:
        source, target, line, _ = self.arrow("extends")
        self.assertEqual((target["id"], source["id"]), (line["startBinding"]["elementId"], line["endBinding"]["elementId"]))

    def test_an_arrow_of_a_contradiction_carries_a_head_at_each_end_and_any_other_at_one(self) -> None:
        heads = [(self.arrow(kind)[2]["startArrowhead"], self.arrow(kind)[2]["endArrowhead"])
                 for kind in ("contradicts", "supports")]
        self.assertEqual([("triangle", "triangle"), (None, "triangle")], heads)

    def test_an_arrow_bends_between_its_ends(self) -> None:
        self.assertEqual(3, len(self.arrow("supports")[2]["points"]))

    def test_an_extension_read_back_from_its_arrow_names_the_note_that_extends_first(self) -> None:
        source, target, line, label = self.arrow("extends")
        board = Board([*card(IDEA), *card(OTHER_IDEA, Point(0, 600))])
        drawn = board.with_elements(ArrowFactory().arrow(board.card(IDEA), board.card(OTHER_IDEA), RelationStyle("extends")))
        self.assertEqual([(IDEA, "extends", OTHER_IDEA)], [relation.triple for _, relation in drawn.arrows()])


class TestBoard(unittest.TestCase):
    def setUp(self) -> None:
        self.first, self.second = card(IDEA), card(OTHER_IDEA, Point(0, 600))
        self.arrow = ArrowFactory().arrow(self.first[0], self.second[0], RelationStyle("extends"))
        self.board = Board([*self.first, *self.second, *self.arrow])

    def test_the_cards_are_read_by_the_notes_they_link(self) -> None:
        self.assertEqual([IDEA, OTHER_IDEA], self.board.linked_titles())

    def test_a_link_the_user_dropped_on_the_board_as_text_is_a_card(self) -> None:
        dropped = {"id": "droppedx", "type": "text", "rawText": "[[A third idea]]", "text": "A third idea", "x": 0, "y": 0}
        self.assertIn("A third idea", Board([*self.board.elements, dropped]).linked_titles())

    def test_an_arrow_between_two_cards_is_read_as_a_relation(self) -> None:
        self.assertEqual([(IDEA, "extends", OTHER_IDEA)], [relation.triple for _, relation in self.board.arrows()])

    def test_an_arrow_bound_to_a_cards_text_is_read_from_its_card(self) -> None:
        self.arrow[0]["startBinding"]["elementId"] = self.first[1]["id"]
        self.assertEqual(IDEA, self.board.arrows()[0][1].source)

    def test_an_arrow_with_a_loose_end_is_no_relation(self) -> None:
        self.arrow[0]["endBinding"] = None
        self.assertEqual([], self.board.arrows())

    def test_an_arrow_is_removed_with_its_label_and_its_bindings(self) -> None:
        erased = self.board.without_arrow(self.arrow[0])
        self.assertEqual(([], []), (erased.arrows(), erased.card(IDEA)["boundElements"]))

    def test_a_card_refaced_keeps_its_place_and_takes_its_new_words(self) -> None:
        refaced = Board(card(IDEA, Point(40, 70))).refaced(IDEA, CardFace(IDEA, "a sharper claim", link=f"[[{IDEA}]]"))
        frame = refaced.card(IDEA)
        self.assertEqual((40, 70, True), (frame["x"], frame["y"],
                                          any(element.get("text") == "a sharper claim" for element in refaced.elements)))

    def test_a_free_point_overlaps_no_card(self) -> None:
        point = self.board.free_point(self.board.card(IDEA))
        frames = [self.first[0], self.second[0]]
        self.assertFalse(any(frame["x"] <= point.x < frame["x"] + frame["width"]
                             and frame["y"] <= point.y < frame["y"] + frame["height"] for frame in frames))

    def test_a_card_without_a_link_is_read_by_its_title_and_its_words(self) -> None:
        titled = CardFactory().card(Point(900, 0), CardFace("Research question", "What is measure?"))
        self.assertEqual([("Research question", "What is measure?")], Board(titled).titled_cards())


class BoardTestCase(WritingTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.create(PAPER)
        self.project = self.tree().named(PAPER)

    def write_note(self, title: str, text: str) -> None:
        self.folders.notes.mkdir(parents=True, exist_ok=True)
        self.folders.atomic_note(title).write_text(text, encoding="utf-8")

    def member(self, title: str, claims: str = "- a claim\n") -> None:
        self.write_note(title, f"{PROJECTS_LINE}{claims}\n# References\n\n# Tasks\n")

    def note_text(self, title: str) -> str:
        return self.folders.atomic_note(title).read_text(encoding="utf-8")

    def sync(self) -> dict:
        syncing = BoardSync(self.tree().named(PAPER), self.folders)
        plan = syncing.plan()
        syncing.apply()
        return plan

    def board_file(self) -> BoardFile:
        return BoardFile(self.project.file.read_text(encoding="utf-8"))

    def board(self) -> Board:
        return Board(self.board_file().elements())

    def redraw(self, board: Board) -> None:
        file = self.board_file()
        self.project.file.write_text(file.written(board.elements, file.state()), encoding="utf-8")

    def relations(self) -> list[tuple]:
        return [relation.triple for _, relation in self.board().arrows()]

    def section_cards(self) -> list[str]:
        return [link.removeprefix(PAPER).lstrip("#") for link in self.board().embedded_links()]


class TestWritesThatFail(BoardTestCase):
    def test_text_that_cannot_be_encoded_leaves_the_file_as_it_was(self) -> None:
        held = self.project.file.read_text(encoding="utf-8")
        with self.assertRaises(UnicodeEncodeError):
            save_text(self.project.file, "half a pair \ud83d")
        self.assertEqual(held, self.project.file.read_text(encoding="utf-8"))

    def test_an_empty_project_file_is_refused_and_not_drawn_anew(self) -> None:
        self.project.file.write_text("", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "is empty"):
            BoardSync(self.tree().named(PAPER), self.folders)
        self.assertEqual("", self.project.file.read_text(encoding="utf-8"))


class TestBackups(BoardTestCase):
    def test_a_board_is_copied_aside_before_it_is_written_over(self) -> None:
        held = self.project.file.read_text(encoding="utf-8")
        self.member(IDEA)
        self.sync()
        self.assertEqual(held, BoardBackups(self.project.file).held()[-1].read_text(encoding="utf-8"))

    def test_a_backup_stands_in_a_folder_of_its_own_and_not_among_the_project_files(self) -> None:
        self.member(IDEA)
        self.sync()
        self.assertNotEqual(self.project.file.parent, BoardBackups(self.project.file).held()[-1].parent)

    def test_an_empty_board_is_not_copied_aside(self) -> None:
        self.project.file.write_text("", encoding="utf-8")
        BoardBackups(self.project.file).keep()
        self.assertEqual([], [backup for backup in BoardBackups(self.project.file).held() if not backup.read_text().strip()])


class TestPlacingBesideACard(BoardTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.member(IDEA)
        self.sync()
        self.write_note(OTHER_IDEA, "- another claim\n\n# References\n\n# Tasks\n")

    def place(self, side: str, anchor: str = IDEA) -> tuple[dict, dict]:
        NotePlacement(self.project, self.folders, OTHER_IDEA, Beside(side, anchor)).apply()
        return self.board().card(anchor), self.board().card(OTHER_IDEA)

    def test_a_card_placed_above_another_stands_over_its_middle_and_clear_of_it(self) -> None:
        anchor, placed = self.place("above")
        self.assertEqual((anchor["x"] + anchor["width"] / 2, True),
                         (placed["x"] + placed["width"] / 2, placed["y"] + placed["height"] < anchor["y"]))

    def test_a_card_placed_left_of_another_stands_on_its_foot_line_and_clear_of_it(self) -> None:
        anchor, placed = self.place("left-of")
        self.assertEqual((round(anchor["y"] + anchor["height"]), True),
                         (round(placed["y"] + placed["height"]), placed["x"] + placed["width"] < anchor["x"]))

    def test_a_card_placed_right_of_another_stands_on_its_foot_line_and_clear_of_it(self) -> None:
        anchor, placed = self.place("right-of")
        self.assertEqual((round(anchor["y"] + anchor["height"]), True),
                         (round(placed["y"] + placed["height"]), placed["x"] > anchor["x"] + anchor["width"]))

    def test_a_card_is_placed_beside_the_research_question_by_its_name(self) -> None:
        NotePlacement(self.project, self.folders, OTHER_IDEA, Beside("right-of", QUESTION)).apply()
        question, placed = self.board().embedded(f"[[{PAPER}#{QUESTION}]]"), self.board().card(OTHER_IDEA)
        self.assertGreater(placed["x"], question["x"] + question["width"])

    def test_a_side_occupied_by_a_card_sends_the_new_card_further_the_same_way(self) -> None:
        self.place("right-of")
        self.write_note("A third idea", "- a third claim\n\n# References\n\n# Tasks\n")
        NotePlacement(self.project, self.folders, "A third idea", Beside("right-of", IDEA)).apply()
        self.assertGreater(self.board().card("A third idea")["x"], self.board().card(OTHER_IDEA)["x"])

    def test_an_anchor_the_board_lacks_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "holds no card"):
            NotePlacement(self.project, self.folders, OTHER_IDEA, Beside("above", "No such note"))

    def test_a_side_that_is_none_of_the_three_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "stands"):
            Beside("beneath", IDEA)


class TestMovingACard(BoardTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.member(OTHER_IDEA)
        self.member(IDEA, f"- a claim\n\t- contradicts [[{OTHER_IDEA}]]\n")
        self.sync()

    def move(self) -> None:
        CardMove(self.project, IDEA, Beside("left-of", OTHER_IDEA)).apply()

    def test_a_moved_card_stands_where_it_was_sent_with_its_words(self) -> None:
        self.move()
        frame = self.board().card(IDEA)
        title = next(element for element in self.board().elements
                     if element["type"] == "text" and element["groupIds"] == frame["groupIds"])
        self.assertEqual((True, True), (frame["x"] + frame["width"] < self.board().card(OTHER_IDEA)["x"],
                                        frame["x"] < title["x"] < frame["x"] + frame["width"]))

    def test_the_arrows_of_a_moved_card_are_drawn_again_between_the_same_notes(self) -> None:
        self.move()
        self.assertEqual([(IDEA, "contradicts", OTHER_IDEA)], self.relations())

    def test_an_arrow_drawn_again_starts_at_the_edge_of_the_card_where_it_now_stands(self) -> None:
        self.move()
        arrow, frame = self.board().arrows()[0][0], self.board().card(IDEA)
        self.assertAlmostEqual(frame["x"] + frame["width"], arrow["x"], delta=20)

    def test_a_sync_after_a_move_changes_no_relation(self) -> None:
        self.move()
        plan = self.sync()
        self.assertEqual(([], [], [], []), (plan["arrows_to_draw"], plan["arrows_to_erase"],
                                            plan["relations_to_write"], plan["relations_to_remove"]))


class TestAnswering(BoardTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.member(IDEA)
        self.member(OTHER_IDEA)
        self.sync()

    def answer(self, question: str = QUESTION) -> dict:
        AnswerArrow(self.project, IDEA, question).apply()
        return next(element for element in self.board().elements if element["type"] == "arrow")

    def test_an_answer_runs_from_the_notes_card_to_the_research_question_with_one_head(self) -> None:
        arrow = self.answer()
        ends = (self.board().card(IDEA)["id"], self.board().embedded(f"[[{PAPER}#{QUESTION}]]")["id"])
        self.assertEqual((ends, (None, "triangle")),
                         ((arrow["startBinding"]["elementId"], arrow["endBinding"]["elementId"]),
                          (arrow["startArrowhead"], arrow["endArrowhead"])))

    def test_an_answer_is_labelled_as_one(self) -> None:
        arrow = self.answer()
        self.assertEqual("answers", self.board().label_of(arrow))

    def test_an_answer_to_another_card_runs_to_that_card(self) -> None:
        self.assertEqual(self.board().card(OTHER_IDEA)["id"], self.answer(OTHER_IDEA)["endBinding"]["elementId"])

    def test_a_second_answer_to_the_same_question_is_refused(self) -> None:
        self.answer()
        with self.assertRaisesRegex(ValueError, "already"):
            AnswerArrow(self.project, IDEA)

    def test_an_answer_to_a_card_the_board_lacks_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "holds no card"):
            AnswerArrow(self.project, IDEA, "No such card")

    def test_a_sync_leaves_an_answer_drawn_and_writes_no_relation_for_it(self) -> None:
        self.answer(OTHER_IDEA)
        plan = self.sync()
        self.assertEqual(([], 1), (plan["relations_to_write"], len(self.board().bound_arrows(self.board().card(IDEA)))))

    def test_a_moved_card_keeps_its_answer_to_the_research_question(self) -> None:
        self.answer()
        CardMove(self.project, IDEA, Beside("left-of", OTHER_IDEA)).apply()
        arrow = self.board().bound_arrows(self.board().card(IDEA))[0]
        self.assertEqual(("answers", self.board().embedded(f"[[{PAPER}#{QUESTION}]]")["id"]),
                         (self.board().label_of(arrow), arrow["endBinding"]["elementId"]))


class TestChangeLog(BoardTestCase):
    def log(self) -> list[str]:
        logged = ProjectFile(self.project.file.read_text(encoding="utf-8")).body(CHANGE_LOG)
        return [line.split(" · ", 1)[1] for line in logged.splitlines()]

    def test_a_note_that_gains_a_card_is_logged_as_added_with_its_link(self) -> None:
        self.member(IDEA)
        self.sync()
        self.assertEqual([f"added [[{IDEA}]]"], self.log())

    def test_an_entry_opens_with_the_day_it_was_written(self) -> None:
        self.member(IDEA)
        self.sync()
        logged = ProjectFile(self.project.file.read_text(encoding="utf-8")).body(CHANGE_LOG)
        self.assertRegex(logged, r"^- \d{4}-\d{2}-\d{2} · added")

    def test_a_sync_that_changes_no_membership_logs_nothing_more(self) -> None:
        self.member(IDEA)
        self.sync()
        self.sync()
        self.assertEqual([f"added [[{IDEA}]]"], self.log())

    def test_a_note_whose_card_the_user_deleted_is_logged_as_removed_after_its_addition(self) -> None:
        self.member(IDEA)
        self.sync()
        self.redraw(Board([element for element in self.board().elements if element["type"] == "embeddable"]))
        self.sync()
        self.assertEqual([f"added [[{IDEA}]]", f"removed [[{IDEA}]]"], self.log())

    def test_a_note_placed_on_the_board_is_logged_as_added(self) -> None:
        self.write_note(IDEA, "- a claim\n\n# References\n\n# Tasks\n")
        NotePlacement(self.project, self.folders, IDEA).apply()
        self.assertEqual([f"added [[{IDEA}]]"], self.log())

    def test_a_note_placed_and_then_synced_is_logged_once(self) -> None:
        self.write_note(IDEA, "- a claim\n\n# References\n\n# Tasks\n")
        NotePlacement(self.project, self.folders, IDEA).apply()
        self.sync()
        self.assertEqual([f"added [[{IDEA}]]"], self.log())

    def test_a_draft_listed_under_the_project_is_logged_as_drafted(self) -> None:
        self.project.list_first_under_drafts("A draft - v01")
        self.assertEqual(["drafted [[A draft - v01]]"], self.log())

    def test_a_renamed_note_adds_no_line_to_the_log(self) -> None:
        self.member(IDEA)
        self.sync()
        self.folders.atomic_note(IDEA).rename(self.folders.atomic_note("A new title"))
        self.sync()
        self.assertEqual([f"added [[{IDEA}]]"], self.log())

    def test_the_log_stands_last_in_the_project_card(self) -> None:
        self.member(IDEA)
        self.sync()
        text = self.project.file.read_text(encoding="utf-8")
        self.assertLess(text.index("## Drafts"), text.index("## Change log"))


class TestMembership(BoardTestCase):
    def test_a_note_that_names_the_project_gains_a_card(self) -> None:
        self.member(IDEA)
        self.sync()
        self.assertEqual([IDEA], self.board().linked_titles())

    def test_the_card_shows_every_claim_of_the_note_and_each_explication_beneath_its_claim(self) -> None:
        self.member(IDEA, "- Construction is proof #review\n\t- not of existence\n- Proof needs intuition\n")
        self.sync()
        self.assertTrue(any(element.get("text") == "• Construction is proof\n   – not of existence\n• Proof needs intuition"
                            for element in self.board().elements))

    def test_a_title_that_runs_over_a_line_is_set_flush_and_a_claim_that_does_hangs_beneath_its_bullet(self) -> None:
        long_claim = "- " + "word " * 30
        self.write_note("A title of an idea long enough to run over one line of its card", f"{PROJECTS_LINE}{long_claim}\n\n# References\n\n# Tasks\n")
        self.sync()
        texts = [element["text"] for element in self.board().elements if element["type"] == "text" and "\n" in element["text"]]
        title = next(text for text in texts if text.startswith("A title"))
        claim = next(text for text in texts if text.startswith("•"))
        self.assertEqual((False, True), (title.split("\n")[1].startswith(" "), claim.split("\n")[1].startswith("   ")))

    def test_a_card_reaches_beneath_the_last_claim_it_shows(self) -> None:
        self.member(IDEA, "- one\n- two\n- three\n")
        self.sync()
        frame = self.board().card(IDEA)
        claims = next(element for element in self.board().elements if element.get("text", "").startswith("• one"))
        self.assertGreater(frame["y"] + frame["height"], claims["y"] + claims["height"])

    def test_a_card_drawn_for_a_note_carries_the_project_into_the_note(self) -> None:
        self.write_note(IDEA, "- a claim\n\n# References\n\n# Tasks\n")
        self.redraw(self.board().with_elements(card(IDEA)))
        self.sync()
        self.assertEqual([PAPER], AtomicNote(self.note_text(IDEA)).links("projects"))

    def test_a_card_deleted_after_a_sync_takes_the_project_out_of_the_note(self) -> None:
        self.member(IDEA)
        self.sync()
        self.redraw(Board([]))
        self.sync()
        self.assertEqual("- a claim\n\n# References\n\n# Tasks\n", self.note_text(IDEA))

    def rename(self, old: str, new: str) -> None:
        self.folders.atomic_note(old).rename(self.folders.atomic_note(new))

    def test_a_note_renamed_after_a_sync_keeps_its_card_under_its_new_title(self) -> None:
        self.member(IDEA)
        self.sync()
        place = (self.board().card(IDEA)["x"], self.board().card(IDEA)["y"])
        self.rename(IDEA, "The idea retitled")
        plan = self.sync()
        card = self.board().card("The idea retitled")
        self.assertEqual(([[IDEA, "The idea retitled"]], [], place, 1),
                         (plan["cards_to_relink"], plan["cards_to_add"], (card["x"], card["y"]),
                          sum(element["type"] == "rectangle" for element in self.board().elements)))

    def test_a_renamed_notes_card_shows_its_new_title(self) -> None:
        self.member(IDEA)
        self.sync()
        self.rename(IDEA, "The idea retitled")
        self.sync()
        self.assertIn("The idea retitled", [element["text"] for element in self.board().elements if element["type"] == "text"])

    def test_two_notes_renamed_at_once_are_not_guessed_at(self) -> None:
        self.member(IDEA)
        self.member(OTHER_IDEA)
        self.sync()
        self.rename(IDEA, "First retitled")
        self.rename(OTHER_IDEA, "Second retitled")
        self.assertEqual([], BoardSync(self.tree().named(PAPER), self.folders).plan()["cards_to_relink"])

    def test_a_link_to_what_is_no_atomic_note_is_left_on_the_board_and_joins_nothing(self) -> None:
        self.redraw(self.board().with_elements(card("Kant - 1998 - Critique of Pure Reason")))
        self.assertEqual([], self.sync()["notes_to_join"])

    def test_a_second_sync_changes_nothing(self) -> None:
        self.member(IDEA)
        self.sync()
        plan = self.sync()
        self.assertEqual([], [value for key, value in plan.items() if key != "project" and value])

    def test_a_sync_leaves_each_card_where_it_stands(self) -> None:
        self.member(IDEA)
        self.sync()
        moved = self.board()
        moved.card(IDEA).update({"x": 1234, "y": 567})
        self.redraw(moved)
        self.member(OTHER_IDEA)
        self.sync()
        self.assertEqual((1234, 567), (self.board().card(IDEA)["x"], self.board().card(IDEA)["y"]))

    def test_the_plan_writes_nothing(self) -> None:
        self.member(IDEA)
        BoardSync(self.project, self.folders).plan()
        self.assertEqual([], self.board().linked_titles())


class TestRelations(BoardTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.member(IDEA)
        self.member(OTHER_IDEA)
        self.sync()

    def relate_in_note(self, line: str) -> None:
        self.member(IDEA, f"- a claim\n{line}\n")

    def test_a_contradiction_the_user_drew_from_the_other_end_is_the_relation_the_note_states(self) -> None:
        self.relate_in_note(f"\t- contradicts [[{OTHER_IDEA}]]")
        board = self.board()
        self.redraw(board.with_elements(ArrowFactory().arrow(board.card(OTHER_IDEA), board.card(IDEA),
                                                             RelationStyle("contradicts"))))
        plan = self.sync()
        self.assertEqual(([], []), (plan["arrows_to_draw"], plan["relations_to_write"]))

    def draw(self, kind: str = "extends") -> None:
        board = self.board()
        self.redraw(board.with_elements(ArrowFactory().arrow(board.card(IDEA), board.card(OTHER_IDEA), RelationStyle(kind))))

    def test_a_relation_written_in_a_note_is_drawn_as_an_arrow(self) -> None:
        self.relate_in_note(f"\t- extends [[{OTHER_IDEA}]]")
        self.sync()
        self.assertEqual([(IDEA, "extends", OTHER_IDEA)], self.relations())

    def test_a_relation_of_a_note_under_review_is_drawn_only_once_the_note_is_reviewed(self) -> None:
        self.relate_in_note(f"\t- extends [[{OTHER_IDEA}]] #review")
        self.sync()
        under_review = len(self.board().arrows())
        self.relate_in_note(f"\t- extends [[{OTHER_IDEA}]]")
        self.sync()
        self.assertEqual((0, ["solid"]), (under_review, [arrow["strokeStyle"] for arrow, _ in self.board().arrows()]))

    def test_an_arrow_the_user_draws_is_written_into_the_note_without_a_review_mark(self) -> None:
        self.draw("supports")
        self.sync()
        self.assertIn(f"\n\t- supports [[{OTHER_IDEA}]]\n", self.note_text(IDEA))

    def test_an_arrow_whose_label_is_no_relation_kind_is_left_and_written_nowhere(self) -> None:
        self.draw("see also")
        self.sync()
        self.assertEqual((1, True), (len(self.board().arrows()), OTHER_IDEA not in self.note_text(IDEA)))

    def test_an_arrow_erased_after_a_sync_takes_its_relation_out_of_the_note(self) -> None:
        self.relate_in_note(f"\t- extends [[{OTHER_IDEA}]]")
        self.sync()
        self.redraw(self.board().without_arrow(self.board().arrows()[0][0]))
        self.sync()
        self.assertNotIn(OTHER_IDEA, self.note_text(IDEA))

    def test_a_relation_deleted_from_its_note_after_a_sync_erases_its_arrow(self) -> None:
        self.relate_in_note(f"\t- extends [[{OTHER_IDEA}]]")
        self.sync()
        self.member(IDEA)
        self.sync()
        self.assertEqual([], self.relations())

    def test_a_relation_inside_a_sentence_is_left_in_the_note_and_its_arrow_drawn_again(self) -> None:
        self.relate_in_note(f"\t- This carries the point further: it extends [[{OTHER_IDEA}]] in one respect.")
        self.sync()
        self.redraw(self.board().without_arrow(self.board().arrows()[0][0]))
        self.sync()
        self.assertEqual((True, [(IDEA, "extends", OTHER_IDEA)]), (OTHER_IDEA in self.note_text(IDEA), self.relations()))

    def test_a_relation_to_a_note_outside_the_project_is_not_drawn(self) -> None:
        self.write_note("An outside idea", "- a claim\n\n# References\n\n# Tasks\n")
        self.relate_in_note("\t- extends [[An outside idea]]")
        self.sync()
        self.assertEqual([], self.relations())


class TestSectionCards(BoardTestCase):
    def shown(self, name: str) -> dict:
        return self.board().embedded(f"[[{PAPER}#{name}]]")

    def title_of(self, name: str) -> dict:
        group = self.shown(name)["groupIds"]
        return next(element for element in self.board().elements if element["type"] == "text" and element["groupIds"] == group)

    def test_a_board_carries_two_markdown_cards_the_project_and_the_research_question(self) -> None:
        self.assertEqual([PROJECT, QUESTION], self.section_cards())

    def test_a_board_carries_no_other_card_until_a_note_joins_it(self) -> None:
        self.assertEqual({"embeddable", "text"}, {element["type"] for element in self.board().elements})

    def test_a_section_card_embeds_its_heading_as_markdown(self) -> None:
        shown = self.shown(PROJECT)
        self.assertEqual(("embeddable", False), (shown["type"], shown["customData"]["mdProps"]["filenameVisible"]))

    def test_a_section_card_lays_see_through_markdown_over_a_fill_the_canvas_draws(self) -> None:
        shown = self.shown(PROJECT)
        props = shown["customData"]["mdProps"]
        self.assertEqual(("#fffdf0", 0, False, False, False),
                         (shown["backgroundColor"], props["backgroundOpacity"], props["backgroundMatchElement"],
                          props["backgroundMatchCanvas"], props["useObsidianDefaults"]))

    def test_a_section_card_carries_its_name_above_it_in_large_black_heavy_type(self) -> None:
        title, shown = self.title_of(PROJECT), self.shown(PROJECT)
        self.assertEqual((PROJECT, "#000000", 7, True, True),
                         (title["text"], title["strokeColor"], title["fontFamily"], title["fontSize"] >= 36,
                          title["y"] + title["height"] <= shown["y"]))

    def test_the_project_card_stands_below_and_to_the_left_of_the_research_question_clear_of_its_level(self) -> None:
        corner, question = self.shown(PROJECT), self.shown(QUESTION)
        self.assertEqual((True, True), (self.title_of(PROJECT)["y"] > question["y"] + question["height"],
                                        question["x"] - (corner["x"] + corner["width"]) > 520))

    def test_the_research_question_shows_its_words_larger_than_the_project_card(self) -> None:
        self.assertGreater(self.shown(QUESTION)["scale"][0], self.shown(PROJECT)["scale"][0])

    def test_the_project_card_is_drawn_tall_enough_for_the_headings_and_lines_it_shows(self) -> None:
        for number in range(12):
            HeadingLine(self.tree().named(PAPER), "drafts", f"- [[A draft - v{number:02}]]").apply()
        file = self.board_file()
        self.project.file.write_text(file.written([], BoardState()), encoding="utf-8")
        self.sync()
        self.assertGreater(self.shown(PROJECT)["height"], 12 * 27)

    def test_the_project_card_grows_downward_to_fit_what_was_written_in_it_and_keeps_its_head(self) -> None:
        before = self.shown(PROJECT)
        CardAddition(self.project, CardText("abstract", "A sentence of the abstract. " * 80, proposed=False)).apply()
        self.sync()
        after = self.shown(PROJECT)
        self.assertEqual((round(before["y"]), True), (round(after["y"]), after["height"] > before["height"]))

    def test_the_title_of_the_project_card_stays_above_it(self) -> None:
        CardAddition(self.project, CardText("abstract", "A sentence of the abstract. " * 80, proposed=False)).apply()
        self.sync()
        self.assertLessEqual(self.title_of(PROJECT)["y"] + self.title_of(PROJECT)["height"], self.shown(PROJECT)["y"])

    def test_the_research_question_grows_downward_and_keeps_its_top(self) -> None:
        before = self.shown(QUESTION)
        for number in range(30):
            CardAddition(self.project, CardText("question", f"A further question, number {number}?", proposed=False)).apply()
        self.sync()
        after = self.shown(QUESTION)
        self.assertEqual((before["y"], True), (after["y"], after["height"] > before["height"]))

    def test_a_section_card_taller_than_its_words_need_keeps_its_height(self) -> None:
        elements = self.board().elements
        next(element for element in elements if element.get("link") == f"[[{PAPER}#{PROJECT}]]")["height"] = 1900
        self.redraw(Board(elements))
        self.sync()
        self.assertEqual(1900, self.shown(PROJECT)["height"])

    def test_a_note_of_a_board_drawn_for_the_first_time_stands_above_the_research_question(self) -> None:
        self.member(IDEA)
        file = self.board_file()
        self.project.file.write_text(file.written([], BoardState()), encoding="utf-8")
        self.sync()
        question, drawn = self.shown(QUESTION), self.board().card(IDEA)
        self.assertEqual((question["x"] + question["width"] / 2, True),
                         (drawn["x"] + drawn["width"] / 2, drawn["y"] + drawn["height"] < question["y"]))

    def test_a_note_without_a_related_card_is_drawn_above_the_research_question(self) -> None:
        self.member(IDEA)
        self.sync()
        question, drawn = self.shown(QUESTION), self.board().card(IDEA)
        self.assertEqual((question["x"] + question["width"] / 2, True),
                         (drawn["x"] + drawn["width"] / 2, drawn["y"] + drawn["height"] < question["y"]))

    def test_a_card_title_is_set_in_black_heavy_type(self) -> None:
        title = card(IDEA)[1]
        self.assertEqual((IDEA, "#000000", 7), (title["text"], title["strokeColor"], title["fontFamily"]))

    def test_a_note_card_shows_the_notes_claims_and_none_of_its_tasks(self) -> None:
        tasks = "".join(f"- [ ] Task {n}\n" for n in range(1, 6))
        self.write_note(IDEA, f"{PROJECTS_LINE}- a claim\n\n# References\n\n# Tasks\n\n{tasks}")
        self.sync()
        texts = [element["text"] for element in self.board().elements if element["type"] == "text"]
        self.assertEqual((True, False, True), ("• a claim" in texts, any("Task 1" in text for text in texts),
                                               any("5 tasks" in text for text in texts)))

    def rewrite_links_with_their_folder_path(self) -> None:
        elements = self.board().elements
        for element in elements:
            if element["type"] == "embeddable":
                element["link"] = element["link"].replace("[[", "[[writing/2 projects/")
        self.redraw(Board(elements))

    def test_a_section_card_whose_link_gained_its_folder_path_is_still_its_headings_card(self) -> None:
        self.rewrite_links_with_their_folder_path()
        self.sync()
        self.assertEqual(2, len(self.board().embedded_links()))

    def test_a_note_is_drawn_above_a_research_question_whose_link_gained_its_folder_path(self) -> None:
        self.rewrite_links_with_their_folder_path()
        self.member(IDEA)
        self.sync()
        question, drawn = self.board().embedded(f"[[writing/2 projects/{PAPER}#{QUESTION}]]"), self.board().card(IDEA)
        self.assertEqual((question["x"] + question["width"] / 2, True),
                         (drawn["x"] + drawn["width"] / 2, drawn["y"] + drawn["height"] < question["y"]))

    def test_a_section_card_the_user_deleted_is_not_drawn_again(self) -> None:
        kept = [element for element in self.board().elements if f"#{PROJECT}" not in (element["link"] or "")]
        self.redraw(Board(kept))
        self.sync()
        self.assertNotIn(PROJECT, self.section_cards())

    def test_a_sync_writes_no_task_and_no_tasks_query_into_the_project_file(self) -> None:
        self.write_note(IDEA, f"{PROJECTS_LINE}- a claim\n\n# References\n\n# Tasks\n\n- [ ] Read on\n")
        self.sync()
        written = self.project.file.read_text(encoding="utf-8")
        self.assertEqual((False, False, False), ("```tasks" in written, "Read on" in written, "Tasks" in written.split("# Excalidraw")[0]))

    def test_a_reading_list_the_project_has_is_left_as_it_stands(self) -> None:
        held = self.folders.reading_lists / f"{PAPER} - Reading list.md"
        held.write_text("# Wanted\n\n- a line of the user's\n", encoding="utf-8")
        self.sync()
        self.assertEqual("# Wanted\n\n- a line of the user's\n", held.read_text(encoding="utf-8"))

    def test_the_project_card_links_the_reading_list(self) -> None:
        self.assertIn(f"## Reading list\n\n[[{PAPER} - Reading list]]", self.project.file.read_text(encoding="utf-8"))

    def test_a_link_embedded_on_the_board_is_no_card_of_a_note(self) -> None:
        self.assertEqual([], self.board().linked_titles())

    def test_the_words_the_assistant_proposes_carry_the_review_mark_and_the_words_the_user_states_none(self) -> None:
        CardAddition(self.project, CardText("question", "What is measure?")).apply()
        CardAddition(self.project, CardText("question", "Is it a category?", proposed=False)).apply()
        self.assertEqual("- What is measure? #review\n- Is it a category?", self.project_file(PAPER).body(QUESTION))

    def test_an_abstract_is_written_as_a_paragraph_under_its_heading_of_the_project(self) -> None:
        CardAddition(self.project, CardText("abstract", "Measure unites quality and quantity.", proposed=False)).apply()
        self.assertIn("# Project\n\n## Abstract\n\nMeasure unites quality and quantity.\n\n## Reading list",
                      self.project.file.read_text(encoding="utf-8"))

    def test_an_open_question_is_written_inside_the_project_card(self) -> None:
        CardAddition(self.project, CardText("open-question", "Does it hold later?", proposed=False)).apply()
        self.assertIn("## Open questions\n\n- Does it hold later?", self.project_file(PAPER).body(PROJECT))

    def test_words_written_under_a_heading_leave_the_drawing_as_it_stands(self) -> None:
        before = self.board().elements
        CardAddition(self.project, CardText("question", "What is measure?")).apply()
        self.assertEqual(before, self.board().elements)


class TestUpgradeAndCards(BoardTestCase):
    def test_an_old_project_file_becomes_a_board_with_its_abstract_and_its_drafts_kept(self) -> None:
        self.project.file.write_text(OLD_PROJECT_FILE, encoding="utf-8")
        self.sync()
        project_file = self.project_file(PAPER)
        self.assertEqual(("Measure unites quality and quantity.", "- [[A draft - v01]]", "drafting", ""),
                         (project_file.body(ABSTRACT), project_file.body(DRAFTS), project_file.status,
                          project_file.body("Outline")))

    def test_a_board_the_user_drew_in_the_projects_folder_becomes_a_project_on_its_first_sync(self) -> None:
        self.project.file.write_text(HAND_DRAWN_BOARD, encoding="utf-8")
        self.sync()
        project_file = self.project_file(PAPER)
        self.assertEqual(("planning", [], DRAWN_BY_HAND), (project_file.status, project_file.parents, self.board().elements[0]))

    def test_the_cards_drawn_beside_what_the_user_drew_overlap_none_of_it(self) -> None:
        self.project.file.write_text(HAND_DRAWN_BOARD, encoding="utf-8")
        self.sync()
        self.assertTrue(all(box["x"] >= DRAWN_BY_HAND["width"] for box in self.board().elements[1:]))

    def test_the_section_cards_are_drawn_once(self) -> None:
        self.project.file.write_text(OLD_PROJECT_FILE, encoding="utf-8")
        self.sync()
        drawn = self.section_cards()
        self.sync()
        self.assertEqual(drawn, self.section_cards())

    def test_a_source_card_links_its_work(self) -> None:
        CardAddition(self.project, CardText("source", "Kant - 1998 - Critique of Pure Reason")).apply()
        self.assertEqual(["Kant - 1998 - Critique of Pure Reason"], self.board().linked_titles())

    def test_a_note_placed_on_a_board_gains_its_card_and_names_the_project(self) -> None:
        self.write_note(IDEA, "- a claim\n\n# References\n\n# Tasks\n")
        NotePlacement(self.project, self.folders, IDEA).apply()
        self.assertEqual(([IDEA], [PAPER]), (self.board().linked_titles(), AtomicNote(self.note_text(IDEA)).links("projects")))

    def test_a_note_with_a_card_on_the_board_is_refused_a_second(self) -> None:
        self.member(IDEA)
        self.sync()
        with self.assertRaisesRegex(ValueError, "has a card"):
            NotePlacement(self.project, self.folders, IDEA)

    def test_a_note_that_is_not_written_is_refused_a_card(self) -> None:
        with self.assertRaisesRegex(ValueError, "no note named"):
            NotePlacement(self.project, self.folders, "An unwritten idea")

    def test_a_card_without_words_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "holds words"):
            CardAddition(self.project, CardText("question", "  "))

    def test_the_reading_names_the_notes_the_other_links_the_cards_and_the_relations(self) -> None:
        self.member(IDEA)
        self.sync()
        CardAddition(self.project, CardText("source", "Kant - 1998 - Critique of Pure Reason")).apply()
        CardAddition(self.project, CardText("question", "What is measure?")).apply()
        reading = BoardReading(self.project, self.folders).as_json()
        self.assertEqual(([IDEA], ["Kant - 1998 - Critique of Pure Reason"], "Research question"),
                         (reading["notes"], reading["other_links"], reading["cards"][0]["title"]))


class TestBoardCommands(BoardTestCase):
    def run_command(self, *argv: str) -> dict:
        out = io.StringIO()
        with mock.patch.object(vault, "WRITING_DIR", self.writing_dir), contextlib.redirect_stdout(out):
            CommandLine().run(list(argv))
        return json.loads(out.getvalue())

    def test_sync_without_apply_plans_and_writes_nothing(self) -> None:
        self.member(IDEA)
        self.assertEqual(([IDEA], False), (self.run_command("sync", PAPER)["cards_to_add"],
                                           bool(self.run_command("board", PAPER)["notes"])))

    def test_sync_with_apply_draws_the_board(self) -> None:
        self.member(IDEA)
        self.run_command("sync", PAPER, "--apply")
        self.assertEqual([IDEA], self.run_command("board", PAPER)["notes"])

    def test_board_reports_where_each_card_stands_and_how_large_it_is(self) -> None:
        self.member(IDEA)
        self.run_command("sync", PAPER, "--apply")
        positions = self.run_command("board", PAPER)["positions"]
        card = self.board().card(IDEA)
        self.assertEqual(([round(card[side]) for side in ("x", "y", "width", "height")], True, True),
                         (positions[IDEA], QUESTION in positions, PROJECT in positions))

    def test_card_with_apply_adds_the_card(self) -> None:
        self.run_command("card", PAPER, "abstract", "Measure unites quality and quantity.", "--stated", "--apply")
        self.assertIn({"title": "Abstract", "body": "Measure unites quality and quantity."},
                      self.run_command("board", PAPER)["cards"])


if __name__ == "__main__":
    unittest.main()
