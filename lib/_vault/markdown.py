from __future__ import annotations

import re

HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})[ \t]+(?P<text>.+?)[ \t]*$")
FOOTNOTE_DEFINITION_RE = re.compile(r"^(?P<label>\[\^[^\]]+\]:[ \t]*)(?P<text>.*)$")
FOOTNOTE_MARK_RE = re.compile(r"\[\^(?P<label>[^\]]+)\](?!:)")
CITATION_LINK_MARK = "↗"
OBSIDIAN_COMMENT_RE = re.compile(r"[ \t]*%%.*?%%[ \t]*")
WIKILINK_RE = re.compile(r"\[\[(?P<target>[^\]|#]+)(?:#[^\]|]*)?(?:\|(?P<shown>(?:\\.|[^\]\\])*))?\]\]")
