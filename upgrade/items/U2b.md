# U2b — No instruction sentence runs over 40 words

| Field | Value |
| --- | --- |
| Status | planned |
| Wave, lane | W5-a: **U2b** |
| Repo | `research-assistant`; `agent-core` for its own instruction text |
| Depends on | U3, U8 |
| Detail | `sources/audit-upgrade-plan.md` §3 U2 (ratchet), §4 row U2b; `PLAN.md` §1 "Audit upgrade plan" |
| Trailer | `Change-class: refactor — <what>` |

## Builds

Every instruction sentence over 40 words, as U3's `prose` row lists it
(about 280 at the plan's count), is split or restated under `clean-prose` and
the STE rules of U2. One file per commit; each file read whole after its edit.
No rule changes meaning: a sentence whose split changes what it binds goes to
`needs-decision`.

**No file grows.** A split MUST NOT grow its file's word count: restate the
sentence shorter, or cut words elsewhere in the same file. U3's `weight` row
checks it.

## Acceptance

| Row | Checked by |
| --- | --- |
| U3's `prose` row finds no sentence over 40 words in the instruction text | CI |
| No instruction file's word count grows | CI: U3's `weight` row against the baseline |
| The audit linter passes | CI |

## Open questions

None known.
