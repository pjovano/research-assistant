export const meta = {
  name: 'upgrade-item',
  description: 'Build one upgrade item: scope it, implement it in a worktree, refute it through three lenses, fix, and open its pull request',
  whenToUse: 'Once per item of upgrade/PLAN.md §3, in the cloud session of the item\'s lane, with args {item: "<id>"}',
  phases: [
    { title: 'Scope', detail: 'one reader: the item file, PLAN.md, the spike record, the code areas' },
    { title: 'Build', detail: 'one implementer in a worktree, on the branch upgrade/<item>' },
    { title: 'Verify', detail: 'three refuters: behaviour, contract, acceptance' },
    { title: 'Fix', detail: 'the implementer on the confirmed findings, at most two rounds' },
    { title: 'Publish', detail: 'push the branch and open the pull request' },
  ],
}

const ITEM_ID_PATTERN = /^[A-Z][0-9]+(\.[0-9]+)?[a-z]?(\+[A-Z][0-9]+)?$/
const MAX_FIX_ROUNDS = 2
const NEEDS_DECISION_LABEL = 'needs-decision'
const PUSH_TIMEOUT_MS = 600000
const CHECK_COMMANDS = [
  '~/.research-vault/venv/bin/python -m unittest discover -s tests',
  '~/.research-vault/venv/bin/ruff check .',
  '~/.research-vault/venv/bin/python .claude/skills/vault-audit/scripts/audit.py lint',
]

const STRINGS = { type: 'array', items: { type: 'string' } }
const CHECKS = {
  type: 'object',
  properties: { suite: { type: 'string' }, ruff: { type: 'string' }, audit: { type: 'string' } },
  required: ['suite', 'ruff', 'audit'],
}
const SCOPE_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['ready', 'blocked', 'deferred'] },
    reason: { type: 'string' },
    repos: STRINGS,
    files: STRINGS,
    tests_to_add: STRINGS,
    risks: STRINGS,
    acceptance: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          row: { type: 'string' },
          checked_by: { type: 'string', enum: ['ci', 'rehearsal', 'pr-body'] },
          how: { type: 'string' },
        },
        required: ['row', 'checked_by', 'how'],
      },
    },
    rehearsal_lines: STRINGS,
    open_questions: STRINGS,
  },
  required: ['status', 'reason', 'repos', 'files', 'tests_to_add', 'risks', 'acceptance', 'rehearsal_lines',
    'open_questions'],
}
const BUILD_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['built', 'failed'] },
    report: { type: 'string' },
    title: { type: 'string' },
    commits: STRINGS,
    checks: CHECKS,
    acceptance: {
      type: 'array',
      items: {
        type: 'object',
        properties: { row: { type: 'string' }, met_by: { type: 'string' } },
        required: ['row', 'met_by'],
      },
    },
    rehearsal_lines: STRINGS,
    open_questions: STRINGS,
  },
  required: ['status', 'report', 'title', 'commits', 'checks', 'acceptance', 'rehearsal_lines', 'open_questions'],
}
const FINDINGS_SCHEMA = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          file: { type: 'string' },
          line: { type: 'integer' },
          claim: { type: 'string' },
          evidence: { type: 'string' },
        },
        required: ['file', 'line', 'claim', 'evidence'],
      },
    },
  },
  required: ['findings'],
}
const FIX_SCHEMA = {
  type: 'object',
  properties: {
    resolved: {
      type: 'array',
      items: {
        type: 'object',
        properties: { claim: { type: 'string' }, how: { type: 'string' } },
        required: ['claim', 'how'],
      },
    },
    unresolved: {
      type: 'array',
      items: {
        type: 'object',
        properties: { claim: { type: 'string' }, why: { type: 'string' } },
        required: ['claim', 'why'],
      },
    },
    checks: CHECKS,
  },
  required: ['resolved', 'unresolved', 'checks'],
}
const PUBLISH_SCHEMA = {
  type: 'object',
  properties: {
    prs: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          repo: { type: 'string' },
          number: { type: 'integer' },
          url: { type: 'string' },
          title: { type: 'string' },
          draft: { type: 'boolean' },
        },
        required: ['repo', 'number', 'url', 'title', 'draft'],
      },
    },
    labelled: { type: 'boolean' },
    auto_merge: { type: 'string', enum: ['enabled', 'refused', 'not-requested'] },
    push_failures: STRINGS,
  },
  required: ['prs', 'labelled', 'auto_merge', 'push_failures'],
}

const LENSES = [
  {
    key: 'behaviour',
    question: [
      'Does `mac-local` behave differently after this branch than on `main`?',
      'Check every path, adapter, default, command, and output the diff touches, as the primary runs it today.',
      'Check invariant 1 (nothing touches the running setup: `~/.research-vault`, the launch agents, `~/.claude/settings.json`, the `research-tools` checkout).',
      'Check invariant 2 (no vault format changes; only additive keys).',
    ].join(' '),
  },
  {
    key: 'contract',
    question: [
      'Does the branch break a rule of the repository\'s contract, `clean-code`, or `clean-prose`?',
      'Check the force words, the sentence forms, and the Vocabulary of every changed instruction line;',
      'every special case (contract §5); every file that names a changed name; a reader for every new field;',
      'a `Defect-class:` or `Change-class:` trailer and an `Upgrade-item:` trailer on every commit.',
    ].join(' '),
  },
  {
    key: 'acceptance',
    question: [
      'Is every acceptance row of the item file met?',
      'A CI row needs a test on the branch that fails without the change and passes with it: run it.',
      'A rehearsal row needs its line in the item\'s own section of `upgrade/rehearsal.md`.',
      'A PR-body row needs the measurement or the output in the build report.',
    ].join(' '),
  },
]

const item = itemId(args)
const branch = `upgrade/${branchSlug(item)}`

phase('Scope')
const scope = await agent(scopePrompt(), { label: `scope:${item}`, phase: 'Scope', schema: SCOPE_SCHEMA })
if (!scope) return stopped('Scope', 'the reader did not return')
if (scope.status !== 'ready') return stopped('Scope', `${scope.status}: ${scope.reason}`)

phase('Build')
const build = await agent(buildPrompt(scope), {
  label: `build:${item}`, phase: 'Build', isolation: 'worktree', schema: BUILD_SCHEMA,
})
if (!build) return stopped('Build', 'the implementer did not return')

const verification = build.status === 'built' ? await verify() : { findings: [], missingLenses: [] }
const unresolved = await fixRounds(verification.findings)

phase('Publish')
const reasons = decisionReasons(build, verification.missingLenses, unresolved)
const publication = await agent(publishPrompt(scope, build, verification.findings, unresolved, reasons), {
  label: `publish:${item}`, phase: 'Publish', schema: PUBLISH_SCHEMA,
})
if (!publication) return stopped('Publish', 'the publisher did not return; the branch is local only')
if (publication.push_failures.length > 0) return pushFailed(publication)

return {
  item,
  branch,
  status: 'published',
  prs: publication.prs,
  auto_merge: publication.auto_merge,
  needs_decision: reasons.length > 0,
  reasons,
  rehearsal_lines: build.rehearsal_lines,
}

function itemId(input) {
  const id = input && input.item
  if (typeof id !== 'string' || !ITEM_ID_PATTERN.test(id)) {
    throw new Error(`upgrade-item needs args {item: "<id>"} naming an item of PLAN.md §3; got ${JSON.stringify(input)}`)
  }
  return id
}

function branchSlug(id) {
  return id.toLowerCase().replace(/[+.]/g, '-')
}

function stopped(phaseName, reason) {
  log(`${item} stopped at ${phaseName}: ${reason}`)
  return { item, branch, status: 'stopped', phase: phaseName, reason }
}

function pushFailed(publication) {
  return { ...stopped('Publish', `a push failed: ${publication.push_failures.join('; ')}`), prs: publication.prs }
}

async function verify() {
  phase('Verify')
  const verdicts = await parallel(LENSES.map(lens => () => agent(refutePrompt(lens), {
    label: `refute:${lens.key}:${item}`, phase: 'Verify', schema: FINDINGS_SCHEMA,
  })))
  const missingLenses = LENSES.filter((lens, index) => !verdicts[index]).map(lens => lens.key)
  const findings = verdicts.flatMap((verdict, index) => verdict
    ? verdict.findings.map(finding => ({ lens: LENSES[index].key, ...finding }))
    : [])
  log(`${item}: ${findings.length} confirmed findings; lenses missing: ${missingLenses.join(', ') || 'none'}`)
  return { findings, missingLenses }
}

async function fixRounds(findings) {
  let open = findings.map(finding => ({
    claim: `[${finding.lens}] ${finding.file}:${finding.line} ${finding.claim}`,
    why: finding.evidence,
  }))
  for (let round = 1; round <= MAX_FIX_ROUNDS && open.length > 0; round++) {
    phase('Fix')
    const result = await agent(fixPrompt(open, round), {
      label: `fix:${item}:${round}`, phase: 'Fix', isolation: 'worktree', schema: FIX_SCHEMA,
    })
    open = result ? result.unresolved : open
  }
  return open
}

function decisionReasons(buildResult, missingLenses, unresolved) {
  const reasons = []
  if (buildResult.status === 'failed') reasons.push(`the build failed: ${buildResult.report}`)
  missingLenses.forEach(lens => reasons.push(`the ${lens} refuter did not return`))
  unresolved.forEach(open => reasons.push(`unresolved after ${MAX_FIX_ROUNDS} fix rounds: ${open.claim} (${open.why})`))
  buildResult.open_questions.forEach(question => reasons.push(`open question: ${question}`))
  return reasons
}

function context() {
  return [
    `You work on item ${item} of the upgrade programme.`,
    '`upgrade/PLAN.md` governs the programme. `upgrade/items/' + item + '.md` states the item.',
    '`upgrade/spikes.md` records what the W0 spike measured. `upgrade/sources/` holds the four detail plans;',
    'where a source plan and PLAN.md differ, PLAN.md wins; where an item file and PLAN.md differ, PLAN.md wins.',
    `The item's branch is \`${branch}\` in every repository the item names.`,
  ].join('\n')
}

function checksRule() {
  return [
    'The session\'s post-edit hook checks the checkout `$CLAUDE_PROJECT_DIR` names, not your worktree.',
    'After every change, run the checks from the root of each worktree you changed, and read their output.',
    'In `research-assistant` the checks are:',
    ...CHECK_COMMANDS.map(command => `- \`${command}\``),
    'In another repository, and after the audit linter has moved to the core, run the commands its contract names.',
  ].join('\n')
}

function commitRule() {
  return [
    'Commit rules:',
    '- The commit title states the rule or the behaviour the change leaves in place.',
    '- The body ends with `Defect-class: <class>` for a fix, or `Change-class: refactor|feature — <what>` otherwise,',
    `  then \`Upgrade-item: ${item}\`, then the attribution lines your session's instructions give.`,
    '- In `upgrade/rehearsal.md`, edit only the section headed by the item\'s ID.',
    '- NEVER edit `upgrade/PLAN.md`, `upgrade/spikes.md`, `upgrade/sources/`, or another item\'s file.',
    '- NEVER push. NEVER commit on `main`.',
    `- Finish with \`git switch --detach\` in every worktree you used, so \`${branch}\` is checked out nowhere.`,
  ].join('\n')
}

function scopePrompt() {
  return [
    context(),
    '',
    'You are the Scope reader. NEVER edit a file, commit, or push.',
    '',
    '1. Read `upgrade/items/' + item + '.md` whole, `upgrade/PLAN.md` §1 to §5, and the Summary of `upgrade/spikes.md`.',
    '2. If the item file\'s Status is `deferred` or `dropped`, return status `deferred`.',
    '3. For each item its "Depends on" row names, run `git fetch origin main` in the repository that item builds in,',
    '   then search `git log origin/main --format=%B` for the trailer `Upgrade-item: <dependency>`.',
    '   If a dependency has no such commit on `main`, return status `blocked` naming it.',
    '4. For each repository the item names, confirm its checkout exists in this session.',
    '   If one is absent, return status `blocked` naming it: the conductor attaches it.',
    '5. Read the source sections and the code and instruction files the item file names.',
    '6. Return status `ready` with: the repositories; the files to change; the tests to add; the risks;',
    '   each acceptance row with how it is checked (`ci`, `rehearsal`, or `pr-body`);',
    '   the rehearsal line IDs; and each question the user must answer before the item can merge.',
  ].join('\n')
}

function buildPrompt(scopeResult) {
  return [
    context(),
    '',
    'You are the implementer. The Scope reader returned:',
    JSON.stringify(scopeResult, null, 2),
    '',
    'You run in a fresh git worktree of the session\'s repository.',
    `1. Run \`git fetch origin\`. If \`origin/${branch}\` exists, run \`git switch -c ${branch} origin/${branch}\`;`,
    `   otherwise run \`git switch -c ${branch} origin/main\`.`,
    '2. For each other repository the item names, add a worktree of it under your scratchpad on the same branch name,',
    '   by the same rule, with `git -C <checkout> worktree add`.',
    '3. Build the item as its file states, under the repository\'s contract (`AGENTS.md`, or `CLAUDE.md` before X2):',
    '   invoke `clean-code` before code and `clean-prose` before instruction text;',
    '   add a test that builds the defect class or pins the behaviour for every CI acceptance row;',
    '   add the item\'s rehearsal lines to its own section of `upgrade/rehearsal.md`.',
    '4. Run the checks. If a check fails, fix the cause; if you cannot, return status `failed` with the output.',
    '5. Commit.',
    '',
    checksRule(),
    '',
    commitRule(),
    '',
    'Return: the status; a report of what changed and each measurement an acceptance row asks for;',
    'a pull request title that states the rule or the behaviour the change leaves in place, never a date, a wave,',
    'an item ID, or a branch name alone; the commit SHAs; each check\'s last line; each acceptance row with what meets it;',
    'the rehearsal line IDs; and each question still open for the user.',
  ].join('\n')
}

function refutePrompt(lens) {
  return [
    context(),
    '',
    `You are the ${lens.key} refuter. Try to show that the branch \`${branch}\` does not do what the item requires.`,
    lens.question,
    '',
    'Rules:',
    `- Read the diff with \`git fetch origin && git diff origin/main...${branch}\` in each repository the item names.`,
    `- To run a check, add a detached worktree with \`git worktree add --detach <scratchpad>/refute-${lens.key} ${branch}\`,`,
    '  run it there, then remove the worktree.',
    '- NEVER commit, push, or edit a tracked file.',
    '- Report a finding only when you confirmed it: a command and its output, or the quoted line.',
    '  If you cannot confirm a suspicion, drop it.',
    '- Report nothing outside your lens.',
    '',
    'Return the confirmed findings, each with its file, its line (0 for a whole-file or branch-level finding),',
    'the claim, and the evidence. An empty list means the lens found nothing.',
  ].join('\n')
}

function fixPrompt(open, round) {
  return [
    context(),
    '',
    `You are the implementer, fix round ${round} of ${MAX_FIX_ROUNDS}. The refuters confirmed these findings:`,
    JSON.stringify(open, null, 2),
    '',
    'You run in a fresh git worktree of the session\'s repository.',
    `1. Run \`git fetch origin\`, then \`git switch ${branch}\`. For another repository the item names,`,
    '   add a worktree of that branch under your scratchpad.',
    '2. Fix each finding at its cause. If a finding does not hold, or its fix needs the user\'s decision,',
    '   leave it unresolved and state why with evidence.',
    '3. Run the checks, then commit.',
    '',
    checksRule(),
    '',
    commitRule(),
    '',
    'Return each finding as resolved (with how) or unresolved (with why), and each check\'s last line.',
  ].join('\n')
}

function publishPrompt(scopeResult, buildResult, findings, unresolved, reasons) {
  const needsDecision = reasons.length > 0
  return [
    context(),
    '',
    'You are the publisher.',
    `1. In each repository the item names, run \`git push -u origin ${branch}\` in a Bash call with \`timeout\``,
    `   ${PUSH_TIMEOUT_MS}: the pre-push hook runs the test suite, the linter, and the audit linter's \`works\` check`,
    '   before the push, and outlasts the default timeout.',
    '   The pre-push hook refused a push if the push\'s output holds `fails; the push is refused`',
    '   or `the hook failed`.',
    '   If the pre-push hook refused the push, the push is a check failure: record it under `push_failures`.',
    '   NEVER retry a push the pre-push hook refused: the same checks fail again on the same commit.',
    '   If the push fails on a network error, retry up to four times, waiting 2, 4, 8, and 16 seconds.',
    '   If the push times out, or still fails on a network error after the fourth retry,',
    '   record it under `push_failures`.',
    '   Record each push failure as its repository, then the last lines of the push\'s output.',
    '   If a repository\'s push failed, open and update no pull request for it.',
    '2. Open one pull request per repository against `main` with the GitHub MCP tools (load them with ToolSearch).',
    '   If an open pull request already has this head branch, update its title and body instead.',
    `   Open it as a draft: ${needsDecision ? 'yes' : 'no'}.`,
    `3. Title: \`${buildResult.title}\`, or a better one that states the rule or the behaviour the change leaves in place.`,
    '4. Body, in this order: what changes; the acceptance table (row, checked by, where); the rehearsal lines added;',
    '   the refuters\' findings and how each was resolved; the open questions; the line `Upgrade-item: ' + item + '`;',
    '   then the pull request attribution your session\'s instructions give.',
    '5. If the item spans `agent-core` and a domain repository, open the core\'s pull request first;',
    '   the domain\'s body names it and states that the domain merges after it.',
    needsDecision
      ? `6. Add the label \`${NEEDS_DECISION_LABEL}\` to each pull request, and post one comment on each that states every reason below, with the context the user needs to answer without opening the diff. End the comment with the attribution footer your session's instructions give.`
      : '6. Add no label. Turn on auto-merge for each pull request with the GitHub MCP tools, merge method `MERGE`:\n   the `Upgrade-item:` trailers must reach `main` in the commits themselves. If auto-merge is refused, say so in\n   your result; the pull request still stands.',
    '',
    'Acceptance rows from the Scope reader:',
    JSON.stringify(scopeResult.acceptance, null, 2),
    'Build report:',
    JSON.stringify({ report: buildResult.report, acceptance: buildResult.acceptance, checks: buildResult.checks,
      rehearsal_lines: buildResult.rehearsal_lines }, null, 2),
    'Refuters\' findings:',
    JSON.stringify(findings, null, 2),
    'Unresolved after the fix rounds:',
    JSON.stringify(unresolved, null, 2),
    'Reasons for the user\'s decision:',
    JSON.stringify(reasons, null, 2),
    '',
    'Return each pull request\'s repository, number, URL, title, and whether it is a draft; whether you labelled them;',
    'whether auto-merge is enabled, was refused, or was not requested; and each push failure.',
  ].join('\n')
}
