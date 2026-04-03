<div align="center">

# pocketDEV

**Your senior developer on call.**

Auto-discovers git repos on your machine. Audits them for real problems. Reports what to fix and why.

![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![License MIT](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![No Dependencies](https://img.shields.io/badge/Dependencies-None-blue)

</div>

---

## How It Works

pocketDEV walks your filesystem, finds every git repo with a remote, and runs a health check on each one. No configuration. No manifest. Point it at a directory and it reports back.

```mermaid
flowchart LR
    A[Scan directories] --> B[Find .git repos]
    B --> C[Filter by remote]
    C --> D{Mode?}
    D -->|audit| E[Health check all repos]
    D -->|review| F[Deep code review of one repo]
    D -->|diagnose| G[Triage a broken repo]
    E --> H[Markdown report]
    F --> H
    G --> H
```

---

## Quick Start

```bash
git clone https://github.com/ionutrosu/claude-tool-auditor.git
cd claude-tool-auditor
python pocketdev.py audit
```

No dependencies to install. Python standard library only.

---

## Three Modes

### `audit` -- Health scan across all repos

Scans every discovered repo for structural and hygiene problems. The default mode. Run it weekly.

```bash
python pocketdev.py audit                      # All repos
python pocketdev.py audit --tool "Finance"     # One repo
python pocketdev.py --scan-dir ~/Projects audit # Custom directory
```

### `review` -- Deep code quality dive into one repo

Inspects a single codebase for complexity hotspots, code smells, security risks, dependency health, and test coverage.

```bash
python pocketdev.py review "Finance"
```

### `diagnose` -- Triage when something is broken

Gathers evidence before guessing: recent commits, test output, dependency state, error logs, environment checks.

```bash
python pocketdev.py diagnose "Transcriptor"
```

---

## What It Checks

### Audit Mode

| Check | What it catches |
|---|---|
| Missing `.gitignore` | Repos at risk of committing build artifacts, secrets, or junk |
| Tracked `node_modules/` | Bloated repos with vendored dependencies in git |
| Large files (>5MB) | Binaries, media, or data files that should use LFS or be gitignored |
| Missing README | Repos with no documentation at all |
| Stale repos | No changes in 30+ days |
| No git remote | Local-only repos with no backup |
| Uncommitted changes | Work sitting in the working tree |
| Unpushed commits | Commits that haven't reached the remote |
| Test detection | Whether tests exist and what framework they use |

### Review Mode

| Check | What it catches |
|---|---|
| Complexity hotspots | Files and functions that are too large (>60 lines per function) |
| TODOs / FIXMEs | Deferred work items with file and line references |
| Hardcoded secrets | API keys, tokens, passwords via pattern matching |
| Console log spam | Leftover `console.log` / `console.debug` calls |
| Commented-out code | Dead code blocks left behind |
| Dependency health | Outdated packages, missing lock files |
| Test coverage ratio | Test files vs. source files |
| Git activity | Commit frequency and contributor breakdown |

### Diagnose Mode

| Check | What it gathers |
|---|---|
| Recent commits | Last 20 commits and diff stats |
| Working tree state | Uncommitted changes that may be causing issues |
| Test execution | Actually runs the test suite and captures output |
| Dependency integrity | Checks if installed deps match declared deps |
| Error logs | Tails recent log files for clues |
| Environment | Missing `.env` files when `.env.example` exists |

---

## Example Output

What an audit report looks like with a mix of healthy and unhealthy repos:

```mermaid
block-beta
  columns 1
  block:header
    A["pocketDEV -- Audit Report"]
  end
  block:summary
    B["4 repos scanned | 3 issues found | 1 test suite passing | 2 with no tests"]
  end
  block:results
    columns 4
    C["Finance\n HEALTHY"]
    D["Chat Widget\n HEALTHY"]
    E["Transcriptor\n 2 ISSUES"]
    F["Backup System\n 1 ISSUE"]
  end
```

```
# pocketDEV -- Audit Report
Generated: 2026-04-03 21:00
Repos scanned: 4

Quick summary: 3 issues found. Tests: 1 passing, 0 failing, 2 with no tests.

---
## Finance -- HEALTHY
Location: ~/Projects/Finance
GitHub: vocality-accounting

Files: 402 | Size: 51831KB | Last changed: 2026-04-03 16:49 UTC

Tests: pytest
Issues: None detected

---
## Chat Widget -- HEALTHY
Location: ~/Projects/Systems/automations/02-lead-gen-chatbot
GitHub: vocality-chat-widget

Files: 34 | Size: 14540KB | Last changed: 2026-04-03 16:50 UTC

Tests: None configured
Issues: None detected

---
## Transcriptor -- 2 ISSUE(S)
Location: ~/Projects/Transcriptor
GitHub: transcriptor-v2

Files: 652 | Size: 117899097KB | Last changed: 2026-04-03 16:50 UTC

Tests: pytest
Issues found:
- Large file: models/whisper-large-v3.bin (2948.2MB)
- Stale -- no changes in 45 days

---
## Backup System -- 1 ISSUE(S)
Location: ~/Projects/Backup System
GitHub: claude-backup-system

Files: 38 | Size: 54520KB | Last changed: 2026-04-01 18:04 UTC
Uncommitted: 2 file(s)

Tests: None configured
Issues found:
- No .gitignore file -- risk of committing junk
```

---

## Claude Code Integration

pocketDEV is designed to work as a Claude Code `SessionStart` hook. After each audit, it writes an `_audit-pending` flag. When Claude Code starts a new session, the hook detects the flag and surfaces the report.

```mermaid
sequenceDiagram
    participant Cron as Scheduled Task
    participant PD as pocketDEV
    participant Flag as _audit-pending
    participant CC as Claude Code
    participant You as Developer

    Cron->>PD: run-pocketdev.sh audit
    PD->>PD: Scan repos, check health
    PD->>Flag: Write timestamp
    Note over CC: Next session starts
    CC->>Flag: Detect pending audit
    CC->>You: "Audit report ready. Say 'review audit' to see findings."
    You->>CC: review audit
    CC->>You: Prioritized findings with fixes and effort estimates
```

When you say **"review audit"**, Claude reads the report as pocketDEV -- a senior developer presenting findings ranked by blast radius: security > correctness > maintainability > style. Each finding comes with a concrete fix, effort estimate, and the question: **your call**.

---

## Scheduling

### Windows (Task Scheduler)

```powershell
$action = New-ScheduledTaskAction -Execute 'C:\Program Files\Git\usr\bin\bash.exe' `
    -Argument '"C:\path\to\run-pocketdev.sh" audit'
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At '8:00PM'
Register-ScheduledTask -TaskName 'pocketDEV Audit' -Action $action -Trigger $trigger
```

### Linux / macOS (cron)

```bash
0 20 * * 0 /path/to/run-pocketdev.sh audit >> /path/to/pocketdev.log 2>&1
```

---

## Options

```
python pocketdev.py [--scan-dir DIR] {audit,review,diagnose}

Global:
  --scan-dir DIR       Directory to scan (repeatable, default: ~/Desktop, ~/Documents, ~/Projects)

audit:
  --tool NAME          Filter by repo name
  --output FILE        Write report to file instead of stdout

review TOOL:
  --output FILE        Write report to file

diagnose TOOL:
  --output FILE        Write report to file
```

---

## Project Structure

| File | Purpose |
|---|---|
| `pocketdev.py` | Core tool -- discovery, audit, review, diagnose |
| `run-pocketdev.sh` | Shell wrapper for cron / Task Scheduler |
| `CLAUDE.md` | System prompt -- defines pocketDEV's persona for Claude Code |
| `_last-audit.md` | Most recent audit report (generated) |
| `_audit-pending` | Flag file for Claude Code session hook (generated) |

---

## License

MIT
