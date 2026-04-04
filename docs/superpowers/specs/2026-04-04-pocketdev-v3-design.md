# pocketDEV v3 — Design Spec

**Date:** 2026-04-04
**Status:** Draft
**Author:** pocketDEV + Ionut

---

## Problem

pocketDEV v2 is a Python linter that checks for surface-level problems (missing .gitignore, large files, stale repos). It doesn't understand code, can't propose features, can't reason about architecture, and stops at hygiene. A senior developer hired to maintain a portfolio of tools would read the code, understand what each tool does, spot architectural weaknesses, propose features, and build an improvement backlog over time. pocketDEV should be that developer.

## Solution

pocketDEV v3 is a **Claude Code scheduled agent** that runs daily at 22:00. Claude is the brain. A Python script gathers structured data (file inventory, git state, test results, dependency health, security scan) so Claude can focus on thinking instead of data collection. Claude reads actual source code, reasons about architecture and efficiency, and writes improvement proposals to a persistent backlog. A changelog gives Claude memory of past decisions so it doesn't repeat itself or contradict prior work.

---

## Architecture

### Two-phase daily run

```
22:00 — Phase 1: Python snapshot (30-60 seconds)
    pocketdev.py snapshot
    Outputs: _snapshot.json (gitignored)

22:01 — Phase 2: Claude agent (5-10 minutes)
    claude -p <agent-prompt.md + _snapshot.json + _changelog.md + _backlog.md>
    Reads actual source code from repos
    Outputs: updated _backlog.md, _urgent.md (if needed)
```

### On-demand mode

User says "review improvements" or "improve Finance":
- Claude reads `_backlog.md` and `_changelog.md`
- Presents proposals ranked by impact
- User approves → Claude implements → writes to `_changelog.md` → marks backlog entry `[DONE]`

---

## Component 1: Snapshot Collector (`pocketdev.py snapshot`)

A new `snapshot` subcommand that replaces the current audit report with structured JSON. The existing `audit`, `review`, and `diagnose` modes remain unchanged for manual use.

### What it collects per repo

```json
{
  "name": "Finance",
  "dir": "/path/to/Finance",
  "remote": "https://github.com/numarulunu/vocality-accounting.git",
  "git": {
    "branch": "master",
    "commits_30d": 5,
    "last_commit_date": "2026-04-04",
    "last_commit_msg": "Clean repo init — code and configs only",
    "uncommitted": 0,
    "unpushed": 0,
    "behind_remote": 0
  },
  "files": {
    "total": 59,
    "by_extension": {".py": 18, ".json": 5, ".txt": 8, ".html": 1},
    "largest": [{"path": "contabilitate.py", "lines": 711}],
    "total_loc": 5200
  },
  "tests": {
    "framework": "pytest",
    "ran": true,
    "passed": true,
    "count": 42,
    "output_tail": "42 passed in 1.14s"
  },
  "security": {
    "secrets_found": 0,
    "pii_found": 0,
    "sensitive_files_tracked": 0,
    "history_issues": 0
  },
  "dependencies": {
    "manager": "pip",
    "count": 0,
    "lockfile": true,
    "outdated": []
  },
  "structure": {
    "has_readme": true,
    "has_license": true,
    "has_gitignore": true,
    "has_tests": true,
    "entrypoints": ["contabilitate.py", "generate_dashboard.py"]
  }
}
```

### What it collects globally

```json
{
  "generated_at": "2026-04-04T22:00:00Z",
  "repos": [...],
  "summary": {
    "total_repos": 11,
    "total_loc": 35000,
    "repos_with_tests": 4,
    "repos_with_critical_issues": 0,
    "repos_changed_today": 3
  }
}
```

This gives Claude everything it needs to prioritize without spending tokens on file listing and git commands.

---

## Component 2: Agent Prompt (`agent-prompt.md`)

The system prompt that defines how Claude thinks during the daily run. This is the core of pocketDEV v3.

### Identity

You are pocketDEV, a senior developer hired to maintain and improve a portfolio of tools. You run every night at 22:00. Your job is to find the highest-impact improvements across all tools and propose them clearly.

### Input context

Each run, you receive:
- `_snapshot.json` — structured data about every repo (files, tests, deps, security, git state)
- `_changelog.md` — history of every past change with reasoning
- `_backlog.md` — current improvement proposals (pending, in-progress, done)

### Thinking process

For each repo that changed since last run (or all repos on first run):

1. **Read the actual source code** of the repo's key files (entrypoints, largest files, config). Don't just look at the snapshot metadata.
2. **Understand what the tool does** and who uses it.
3. **Evaluate against these dimensions:**
   - **Architecture:** Is the structure right? Are responsibilities clear? Are there god-functions that should be split?
   - **Features:** What's obviously missing? What would a user expect that isn't there?
   - **Efficiency:** Are there performance bottlenecks? Redundant operations? Files read multiple times?
   - **Reliability:** What happens when things fail? Are there retries? Graceful degradation? Timeout handling?
   - **Security:** Secrets, PII, input validation at boundaries.
   - **Tests:** What's tested? What critical path has no tests?
   - **Dependencies:** Anything outdated, unused, or missing?
4. **Check the changelog** — has this area been worked on recently? Don't propose what was just done or explicitly rejected.
5. **Check the backlog** — is there already a proposal for this? If so, update it rather than duplicating.

### Output rules

- Write new proposals to `_backlog.md` in the format specified below.
- Each proposal must have: impact (high/medium/low), effort estimate, what to change, why it matters.
- Maximum 3 new proposals per repo per run. Quality over quantity.
- If something is urgent (security, broken tests, data loss risk), write it to `_urgent.md` instead.
- Prune stale backlog entries (>30 days old, never approved) — move to a `## Archived` section.
- Never implement anything. Only propose.

### Tone

Direct, clinical, specific. File paths and line numbers. No filler. Propose the fix, explain the impact, estimate the effort, stop.

---

## Component 3: Backlog (`_backlog.md`)

Persistent file, tracked in git. Accumulates over time.

### Format

```markdown
# pocketDEV Improvement Backlog
Last updated: 2026-04-04 22:00

## Finance — PFA Accounting Engine

### [NEW] Add automatic BNR rate refresh
**Impact:** High | **Effort:** 1 hour
**What:** Add scheduled fetch from BNR API to update bnr_rates.json daily.
**Why:** The rates file is 12,340 lines of manually maintained JSON. Rates go stale.
**Added:** 2026-04-04

### [APPROVED] Split main() into pipeline stages
**Impact:** Medium | **Effort:** 2 hours
**What:** Extract parse, validate, calculate, output stages from the 596-line main().
**Why:** Untestable monolith. Can't modify one stage without risking the others.
**Added:** 2026-04-03 | **Approved:** 2026-04-04

### [DONE] Remove PII from git history
**Impact:** Critical | **Effort:** 30 min
**What:** Fresh repo init, purged 331 personal financial files.
**Why:** Bank statements, IBANs, client emails were on GitHub.
**Added:** 2026-04-04 | **Done:** 2026-04-04

---

## Archived

### [STALE] Add Excel export to dashboard
**Impact:** Low | **Effort:** 3 hours
**Reason archived:** Proposed 2026-03-01, never prioritized. Dashboard HTML is sufficient.
```

### Statuses

| Status | Meaning |
|---|---|
| `[NEW]` | Just proposed, not yet reviewed by user |
| `[APPROVED]` | User approved, ready to implement |
| `[IN PROGRESS]` | Currently being worked on |
| `[DONE]` | Implemented and verified |
| `[REJECTED]` | User explicitly declined |
| `[STALE]` | >30 days without action, archived |

---

## Component 4: Changelog (`_changelog.md`)

Persistent narrative log of every change made to every tool. Written by Claude after each implementation. Gives future runs context about past decisions.

### Format

```markdown
# pocketDEV Changelog

## 2026-04-04 — Finance v1.0 (history rewrite)
**What changed:** Fresh git init. Purged 331 personal financial files from history.
**Why:** Initial commit included Input/ directory with bank statements, invoices,
Stripe client emails, IBAN. Already pushed to GitHub.
**Impact:** Repo went from 390 files to 59. All PII eliminated from git history.
**Decision context:** pocketDEV security audit flagged 10 critical PII leaks.
User approved fresh start approach over git filter-repo (only 4 commits).

## 2026-04-04 — Backup System v2.0
**What changed:** Refactored memory-sync.py — extracted run() into 4 functions,
added 5MB digest size cap, fixed username parsing bug for multi-word Windows usernames.
Separated backup-all-tools.sh into standalone Git Sync project.
**Why:** run() was 103 lines doing 5 things. Digest files growing unbounded (50MB).
backup-all-tools had nothing to do with conversation digests.
**Impact:** 22 tests added. Digest size capped. Clean project separation.
**Decision context:** pocketDEV deep review identified 6 improvements. User approved all.
```

### Fields per entry

- **What changed:** Factual description of the change
- **Why:** The problem it solved
- **Impact:** Measurable outcome
- **Decision context:** What led to this decision — audit finding, user request, backlog item. Includes rejected alternatives if relevant ("chose fresh start over filter-repo because only 4 commits").

---

## Component 5: Urgent Flag (`_urgent.md`)

Written only when the daily run finds something that can't wait for the next interactive session.

- Security vulnerabilities (secrets committed, PII exposed)
- Broken tests that were passing yesterday
- Dependency with known CVE
- Repo that disappeared or lost its remote

SessionStart hook checks for this file and alerts immediately.

### Format

```markdown
# URGENT — pocketDEV 2026-04-04 22:00

## Finance — Tests Failing
**Severity:** High
**What:** pytest reports 3 failures in test_reconciliation.py.
Tests were passing at last run (2026-04-03).
**Likely cause:** Commit abc1234 changed bank_parser.py output format.
**Suggested fix:** Update test assertions to match new format.
```

---

## Component 6: Shell Wrapper (`run-pocketdev.sh`)

```bash
#!/bin/bash
# Phase 1: Gather data
python pocketdev.py snapshot --output _snapshot.json

# Phase 2: Claude agent thinks
claude -p "$(cat agent-prompt.md)" \
  --allowedTools "Read,Glob,Grep,Bash,Write,Edit" \
  --input-file _snapshot.json \
  --input-file _changelog.md \
  --input-file _backlog.md
```

The exact `claude` CLI invocation will depend on what flags are available for headless/scheduled mode. The `/schedule` skill may be the right mechanism instead of a bash wrapper.

---

## Component 7: Scheduling

Daily at 22:00 via Windows Task Scheduler (or Claude Code's `/schedule` if it supports this pattern):

```powershell
$action = New-ScheduledTaskAction -Execute 'C:\Program Files\Git\usr\bin\bash.exe' `
    -Argument '"C:\Users\Gaming PC\Desktop\Claude\Tool Auditor\run-pocketdev.sh"'
$trigger = New-ScheduledTaskTrigger -Daily -At '10:00PM'
Register-ScheduledTask -TaskName 'pocketDEV Daily' -Action $action -Trigger $trigger
```

---

## Integration: SessionStart Hook

On every new Claude Code session, check:
1. `_urgent.md` exists and non-empty → "pocketDEV found urgent issues. Say 'review urgent' to see them."
2. `_backlog.md` has `[NEW]` entries → "pocketDEV proposed N improvements overnight. Say 'review improvements' to see them."

---

## What stays from v2

- `audit` mode — security + hygiene scan (now enhanced with PII/secret/history checks)
- `review` mode — deep code quality review of one tool
- `diagnose` mode — broken tool triage
- `snapshot` mode — NEW, structured JSON for the Claude agent

The Python script remains the data layer. Claude is the intelligence layer.

---

## Success criteria

1. Daily run completes in under 10 minutes
2. Backlog grows with real, actionable proposals (not "add README" noise)
3. Changelog gives future Claude sessions enough context to avoid redundant proposals
4. User can say "review improvements" and get a ranked list with effort estimates
5. User can approve an item and Claude implements it in the same session
6. Security issues surface immediately via _urgent.md
