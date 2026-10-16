from __future__ import annotations

import re

import vault

CITATION_LINK_PATTERN = rf"[ \t]*\[\[(?P<work>[^\]|]+)\|{re.escape(vault.CITATION_LINK_MARK)}\]\]"
CITATION_LINK_RE = re.compile(CITATION_LINK_PATTERN)
