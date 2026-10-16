# P7h — The test vaults build a `Vault` instead of patching paths

| Field | Value |
| --- | --- |
| Status | deferred |
| Wave, lane | W6: not in this round |
| Repo | `research-assistant` |
| Depends on | P7f |
| Detail | `sources/hexagonal-ports-plan.md` §4 PR 7 step 7h, §5 row P7; `PLAN.md` §1 "Hexagonal ports plan" (92 test files patch the constants) |
| Trailer | `Change-class: refactor — <what>` |

**The item workflow MUST NOT build this item.** It is deferred: `PLAN.md` §3,
"Deferred", names the need it waits for. It runs only if the user says so.

## Builds

- `tests/_vaults.py`'s `TempVault` builds a `Vault` directly instead of
  patching the path attributes.
- The test files that patch the constants take that `Vault`.
- The CI empty-vault action keeps setting `vault_dir`.

## Acceptance

| Row | Checked by |
| --- | --- |
| No test patches a path attribute | CI: a `git grep` test over `tests/` |
| The suite passes with the same test count as before | CI; the PR body states both counts |

## Open questions

None known.
