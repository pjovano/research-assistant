from __future__ import annotations

import json
import unittest

from _workflow_source import JsRuntime, WorkflowSource

UNREADABLE = "unreadable"
LINE = {"state": "batch", "works": [{"basename": "A - 2020 - B", "from": "extract"}]}


class JsonLineParser:
    def __init__(self, runtime: JsRuntime) -> None:
        self._runtime = runtime

    def parse(self, reply: str) -> object:
        source = WorkflowSource.ingest().declarations("CODE_FENCE_LINE", "SURROUNDING_BACKTICKS", "jsonLineOf",
                                                                 "parsedReplyOf", "isJsonObject")
        program = (f"{source}\ntry {{ console.log(JSON.stringify(jsonLineOf({json.dumps(reply)}))) }} "
                   f"catch {{ console.log('{UNREADABLE}') }}")
        printed = self._runtime.printed(program)
        return UNREADABLE if printed == UNREADABLE else json.loads(printed)


class RelayReplyDecoratedAroundItsJsonLine(unittest.TestCase):
    def setUp(self) -> None:
        runtime = JsRuntime()
        runtime.require(self)
        self.parser = JsonLineParser(runtime)

    def test_a_bare_json_line_is_read(self) -> None:
        self.assertEqual(LINE, self.parser.parse(json.dumps(LINE)))

    def test_a_json_line_wrapped_in_backticks_is_read(self) -> None:
        self.assertEqual(LINE, self.parser.parse(f"`{json.dumps(LINE)}`"))

    def test_a_json_line_inside_a_code_fence_is_read(self) -> None:
        self.assertEqual(LINE, self.parser.parse(f"```json\n{json.dumps(LINE)}\n```"))

    def test_a_json_line_after_prose_is_read(self) -> None:
        self.assertEqual(LINE, self.parser.parse(f"The command printed:\n`{json.dumps(LINE)}`"))

    def test_a_json_line_printed_over_several_lines_is_read(self) -> None:
        self.assertEqual(LINE, self.parser.parse(json.dumps(LINE, indent=2)))

    def test_prose_before_a_json_object_over_several_lines_is_unreadable(self) -> None:
        self.assertEqual(UNREADABLE, self.parser.parse("The command printed:\n" + json.dumps(LINE, indent=2)))

    def test_a_reply_ending_in_no_json_line_is_unreadable(self) -> None:
        self.assertEqual(UNREADABLE, self.parser.parse("}"))

    def test_a_reply_ending_in_a_json_string_is_unreadable(self) -> None:
        self.assertEqual(UNREADABLE, self.parser.parse(json.dumps("~/scratch/scope-verdicts-2.json")))

    def test_a_reply_ending_in_a_json_list_is_unreadable(self) -> None:
        self.assertEqual(UNREADABLE, self.parser.parse(json.dumps([LINE])))

    def test_an_empty_reply_is_unreadable(self) -> None:
        self.assertEqual(UNREADABLE, self.parser.parse(""))


if __name__ == "__main__":
    unittest.main()
