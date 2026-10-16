# P7g — The path shim is deleted, and a lint rule refuses a new path constant

| Field | Value |
| --- | --- |
| Status | deferred |
| Wave, lane | W6: not in this round |
| Repo | `research-assistant` |
| Depends on | P7h, U3 |
| Detail | `sources/hexagonal-ports-plan.md` §4 PR 7 step 7g, §5 row P7 |
| Trailer | `Change-class: refactor — <what>` |

**The item workflow MUST NOT build this item.** It is deferred: `PLAN.md` §3,
"Deferred", names the need it waits for. It runs only if the user says so.

`PLAN.md` §3 names P7f and U3. P7h, the last slice of W3-b, also precedes this
item: the shim's deletion breaks every test that still patches a constant.

## Builds

- The module-level constants of `_vault/paths.py` are deleted.
- The research `audit/checks.py` gains a lint rule that refuses a new
  module-level path constant in `lib/` or the skills.

## Acceptance

| Row | Checked by |
| --- | --- |
| No module-level path constant in `lib/` or the skills | CI: the lint rule |
| The lint rule passes | CI |
| An `ingest` dry run resolves every path | Rehearsal: R-X3-1 covers it |

## Open questions

None known.
