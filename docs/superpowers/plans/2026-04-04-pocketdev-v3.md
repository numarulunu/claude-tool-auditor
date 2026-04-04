# pocketDEV v3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform pocketDEV from a Python linter into a Claude-powered senior developer that runs daily, reads actual code, proposes architecture/feature/efficiency improvements, and maintains a persistent backlog with full decision history.

**Architecture:** Two-phase daily run. Phase 1: Python `snapshot` subcommand gathers structured data (30s). Phase 2: Claude headless session (`claude -p`) reads the snapshot + source code + changelog + backlog, then writes improvement proposals. Persistent `_backlog.md` and `_changelog.md` give Claude memory across runs.

**Tech Stack:** Python 3.10+ (snapshot collector), Claude Code CLI headless mode (`claude -p`), bash wrapper, Windows Task Scheduler for daily 22:00.

---

### Task 1: Add `snapshot` subcommand to pocketdev.py

**Files:**
- Modify: `pocketdev.py` — add `snapshot` subparser and `snapshot_repo()` / `snapshot_all()` functions

- [ ] **Step 1: Add snapshot subparser to CLI**

In `main()`, after the `diagnose` subparser block, add:

```python
# snapshot
p_snapshot = subparsers.add_parser("snapshot", help="Generate structured JSON for Claude agent")
p_snapshot.add_argument("--output", type=str, default=None,
                       help="Write snapshot to file (default: stdout)")
```

- [ ] **Step 2: Write `snapshot_repo()` function**

Add this function after `run_tests()`. It reuses existing helpers but outputs structured JSON instead of markdown:

```python
def snapshot_repo(repo):
    """Generate structured JSON snapshot of one repo for Claude agent."""
    d = Path(repo["dir"])
    if not d.exists():
        return {"name": repo["name"], "dir": repo["dir"], "exists": False}

    tracked = get_tracked_files(repo["dir"])

    # Git info
    git_info = {"branch": None, "commits_30d": 0, "last_commit_date": None,
                "last_commit_msg": None, "uncommitted": 0, "unpushed": 0, "behind_remote": 0}

    code, stdout, _ = run_cmd(["git", "branch", "--show-current"], cwd=repo["dir"])
    if code == 0:
        git_info["branch"] = stdout.strip()

    code, stdout, _ = run_cmd(["git", "log", "--oneline", "--since=30 days ago", "--no-merges"], cwd=repo["dir"])
    if code == 0 and stdout:
        git_info["commits_30d"] = len(stdout.splitlines())

    code, stdout, _ = run_cmd(["git", "log", "-1", "--format=%ai|||%s"], cwd=repo["dir"])
    if code == 0 and stdout and "|||" in stdout:
        parts = stdout.split("|||", 1)
        git_info["last_commit_date"] = parts[0].strip()[:10]
        git_info["last_commit_msg"] = parts[1].strip()[:120]

    code, stdout, _ = run_cmd(["git", "status", "--porcelain"], cwd=repo["dir"])
    if code == 0 and stdout:
        git_info["uncommitted"] = len(stdout.splitlines())

    code, stdout, _ = run_cmd(["git", "log", "--oneline", "@{u}..HEAD"], cwd=repo["dir"])
    if code == 0 and stdout:
        git_info["unpushed"] = len(stdout.splitlines())

    if repo["remote"]:
        code, stdout, _ = run_cmd(["git", "rev-list", "--count", "HEAD..@{u}"], cwd=repo["dir"])
        if code == 0 and stdout.strip().isdigit():
            git_info["behind_remote"] = int(stdout.strip())

    # File stats
    ext_counts = Counter()
    total_loc = 0
    largest = []
    for f, rel in iter_source_files(repo["dir"]):
        ext_counts[f.suffix.lower()] += 1
        content = read_file_safe(f)
        if content:
            loc = len(content.splitlines())
            total_loc += loc
            largest.append({"path": rel, "lines": loc})

    largest.sort(key=lambda x: x["lines"], reverse=True)

    # Tests
    tests_info = detect_tests(d)
    test_result = run_tests(d, tests_info)

    # Security
    secrets = scan_secrets(repo["dir"], d, tracked)
    pii = scan_pii(repo["dir"], d, tracked)
    history = scan_history(repo["dir"])

    sensitive_tracked = sum(1 for tf in tracked
                          if Path(tf).name.lower() in SENSITIVE_FILES
                          or Path(tf).suffix.lower() in SENSITIVE_EXTENSIONS)

    # Dependencies
    deps = check_dependencies(d)

    # Structure
    entrypoints = []
    for tf in tracked:
        p = Path(tf)
        if p.suffix == ".py" and p.name not in ("__init__.py", "setup.py", "conftest.py"):
            fpath = d / tf.replace("/", os.sep)
            content = read_file_safe(fpath, max_bytes=5000)
            if content and ('if __name__' in content or 'def main' in content):
                entrypoints.append(tf)
        elif p.suffix == ".sh":
            entrypoints.append(tf)
    if (d / "package.json").exists():
        try:
            pkg = json.loads((d / "package.json").read_text(encoding="utf-8"))
            for script_name in ("start", "dev", "serve"):
                if script_name in pkg.get("scripts", {}):
                    entrypoints.append(f"npm run {script_name}")
                    break
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "name": repo["name"],
        "dir": repo["dir"],
        "remote": repo["remote"],
        "git": git_info,
        "files": {
            "total": len(tracked),
            "by_extension": dict(ext_counts.most_common(15)),
            "largest": largest[:10],
            "total_loc": total_loc,
        },
        "tests": {
            "framework": tests_info.get("framework"),
            "has_tests": tests_info.get("has_tests", False),
            "ran": test_result.get("ran", False),
            "passed": test_result.get("passed"),
            "output_tail": test_result.get("output", "")[-300:] if test_result.get("output") else None,
        },
        "security": {
            "secrets_found": len(secrets),
            "pii_found": len(pii),
            "sensitive_files_tracked": sensitive_tracked,
            "history_issues": len(history),
            "details": [s["type"] + ": " + s["file"] for s in secrets[:5]]
                     + [p["type"] + ": " + p["file"] for p in pii[:5]]
                     + history[:5],
        },
        "dependencies": {
            "manager": deps["manager"],
            "count": deps["count"],
            "lockfile": deps["lockfile"],
            "outdated": deps["outdated"][:10],
        },
        "structure": {
            "has_readme": any((d / n).exists() for n in ["README.md", "readme.md", "README.txt", "README"]),
            "has_license": any((d / n).exists() for n in ["LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE"]),
            "has_gitignore": (d / ".gitignore").exists(),
            "has_tests": tests_info.get("has_tests", False),
            "entrypoints": entrypoints[:5],
        },
    }
```

- [ ] **Step 3: Write `snapshot_all()` function and wire into CLI**

```python
def snapshot_all(repos):
    """Generate full portfolio snapshot as JSON."""
    repo_snapshots = []
    for repo in repos:
        print(f"  Snapshotting {repo['name']}...", file=sys.stderr)
        repo_snapshots.append(snapshot_repo(repo))

    changed_today = sum(1 for r in repo_snapshots
                       if r.get("git", {}).get("last_commit_date") == datetime.now().strftime("%Y-%m-%d"))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_repos": len(repo_snapshots),
            "total_loc": sum(r.get("files", {}).get("total_loc", 0) for r in repo_snapshots),
            "repos_with_tests": sum(1 for r in repo_snapshots if r.get("tests", {}).get("has_tests")),
            "repos_with_critical_issues": sum(1 for r in repo_snapshots
                                             if r.get("security", {}).get("secrets_found", 0) > 0
                                             or r.get("security", {}).get("pii_found", 0) > 0),
            "repos_changed_today": changed_today,
        },
        "repos": repo_snapshots,
    }
```

In `main()`, add the snapshot handler after the diagnose block:

```python
    # --- SNAPSHOT ---
    elif args.mode == "snapshot":
        snapshot = snapshot_all(repos)
        report = json.dumps(snapshot, indent=2, default=str)
```

- [ ] **Step 4: Test the snapshot subcommand**

Run: `python pocketdev.py snapshot --output _snapshot.json`
Expected: JSON file with structured data for all 11 repos.
Verify: `python -c "import json; d=json.load(open('_snapshot.json')); print(d['summary']); print([r['name'] for r in d['repos']])"`

- [ ] **Step 5: Add `_snapshot.json` to .gitignore**

Append `_snapshot.json` to `.gitignore`.

- [ ] **Step 6: Commit**

```bash
git add pocketdev.py .gitignore
git commit -m "feat: add snapshot subcommand for Claude agent consumption"
```

---

### Task 2: Create the agent prompt

**Files:**
- Create: `agent-prompt.md`

- [ ] **Step 1: Write agent-prompt.md**

```markdown
# pocketDEV — Senior Developer Agent

You are pocketDEV, a senior developer hired to maintain and improve a portfolio of tools. You run every night. Your job is to find the highest-impact improvements across all tools and propose them clearly.

## Your Input

You have access to:
1. **This prompt** — your identity and rules
2. **_snapshot.json** — structured data about every repo (files, tests, deps, security, git state)
3. **_changelog.md** — history of every past change with reasoning
4. **_backlog.md** — current improvement proposals and their statuses

## Your Process

### Step 1: Read context
- Read `_snapshot.json` to see the state of all repos
- Read `_changelog.md` to understand what's been done and why
- Read `_backlog.md` to see existing proposals

### Step 2: Identify repos that need attention
Prioritize repos that:
- Changed since last run (new commits)
- Have failing tests
- Have security issues
- Were recently worked on (momentum — propose next steps)
- Haven't been touched in a while (check if they're rotting)

### Step 3: For each repo needing attention, read the actual code
Don't just look at the snapshot metadata. Read the key source files:
- Entrypoints listed in the snapshot
- The largest files (complexity hotspots)
- Test files (what's covered, what's not)
- Config files (are they sane?)

### Step 4: Think like a senior developer
For each repo, evaluate:
- **Architecture:** Is the structure right for what this tool does? God-functions? Wrong abstractions? Missing separation of concerns?
- **Features:** What's obviously missing? What would make this tool 2x more useful?
- **Efficiency:** Redundant operations? Files read multiple times? Unnecessary network calls? Slow loops?
- **Reliability:** What happens when things fail? Missing retries? No timeout handling? Silent failures?
- **Security:** Secrets, PII, unvalidated input at boundaries.
- **Tests:** What critical path has no tests? What test would catch the most likely regression?
- **Dependencies:** Outdated? Unused? Missing?

### Step 5: Check history before proposing
Before writing a new proposal:
1. Check `_changelog.md` — was this already done? Was it explicitly rejected?
2. Check `_backlog.md` — is there already a proposal for this? If yes, update it instead of duplicating.

### Step 6: Write proposals
For each new improvement, append to `_backlog.md` using this exact format:

```
### [NEW] Title of improvement
**Impact:** High/Medium/Low | **Effort:** time estimate
**What:** Concrete description of the change. File paths. Line numbers if relevant.
**Why:** The problem this solves. Why it matters.
**Added:** YYYY-MM-DD
```

Rules:
- Maximum 3 new proposals per repo per run. Quality over quantity.
- Don't propose trivial hygiene (add README, add docstring). Propose things that make the tool work better.
- Be specific. "Refactor main()" is not a proposal. "Extract the 596-line main() in contabilitate.py into parse_bank_statement(), validate_entries(), calculate_taxes(), and generate_output() — each independently testable" is a proposal.
- Include effort estimates that are honest. Quick fix = under 30 min. Small project = 1-3 hours. Big project = 1+ days.

### Step 7: Handle urgent issues
If you find something that can't wait (security vulnerability, broken tests that were passing, data loss risk):
- Write to `_urgent.md` with severity, what's wrong, likely cause, and suggested fix.
- These get surfaced to the user immediately on next session start.

### Step 8: Prune stale backlog entries
Any `[NEW]` entry older than 30 days that was never approved: move to `## Archived` section at bottom of `_backlog.md` with status `[STALE]`.

## Output Rules

- Edit `_backlog.md` to add/update proposals. Use the Edit tool.
- Create or update `_urgent.md` only if urgent issues exist. If none, don't create the file.
- Never edit `_changelog.md` — that's written by the user's session after implementing changes.
- Never implement anything. Only propose.
- Never push to git. Only write local files.

## Tone

Direct, clinical, specific. File paths and line numbers. No filler, no "consider", no "might want to". State the problem, state the fix, state the effort. Stop.
```

- [ ] **Step 2: Commit**

```bash
git add agent-prompt.md
git commit -m "feat: add Claude agent system prompt for daily improvement runs"
```

---

### Task 3: Create the shell wrapper

**Files:**
- Modify: `run-pocketdev.sh` — rewrite to support both old modes and new agent mode

- [ ] **Step 1: Rewrite run-pocketdev.sh**

```bash
#!/bin/bash
set -uo pipefail

# run-pocketdev.sh — Run pocketDEV in any mode.
#
# Usage:
#   ./run-pocketdev.sh agent                    # Full daily run (snapshot + Claude)
#   ./run-pocketdev.sh snapshot                 # Just generate snapshot
#   ./run-pocketdev.sh audit                    # Audit all tools
#   ./run-pocketdev.sh audit "Finance"          # Audit one tool
#   ./run-pocketdev.sh review "Finance"         # Deep review
#   ./run-pocketdev.sh diagnose "Transcriptor"  # Diagnose

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="/c/Python314/python"
LOGFILE="$SCRIPT_DIR/_pocketdev.log"

MODE="${1:-agent}"
TOOL="${2:-}"

exec >> "$LOGFILE" 2>&1
echo "=== pocketDEV $MODE — $(date) ==="

case "$MODE" in
    agent)
        # Phase 1: Generate snapshot
        echo "  Phase 1: Generating snapshot..."
        $PYTHON "$SCRIPT_DIR/pocketdev.py" snapshot --output "$SCRIPT_DIR/_snapshot.json"
        if [ $? -ne 0 ]; then
            echo "ERROR: Snapshot generation failed."
            exit 1
        fi
        echo "  Snapshot saved."

        # Phase 2: Claude agent reads code and proposes improvements
        echo "  Phase 2: Launching Claude agent..."

        # Build the prompt with context file references
        AGENT_PROMPT=$(cat "$SCRIPT_DIR/agent-prompt.md")

        # Ensure backlog and changelog exist
        touch "$SCRIPT_DIR/_backlog.md"
        touch "$SCRIPT_DIR/_changelog.md"

        claude -p \
            --append-system-prompt "$AGENT_PROMPT" \
            --allowedTools "Read,Glob,Grep,Edit,Write,Bash(git log:*),Bash(git diff:*),Bash(git show:*)" \
            --max-budget-usd 5 \
            "You are pocketDEV running your daily improvement cycle.

Read these files to get your context:
1. $SCRIPT_DIR/_snapshot.json (structured repo data)
2. $SCRIPT_DIR/_changelog.md (history of past changes)
3. $SCRIPT_DIR/_backlog.md (current improvement proposals)

Then read the actual source code of repos that need attention. Propose improvements by editing _backlog.md. If anything is urgent, write _urgent.md.

Today is $(date '+%Y-%m-%d'). Work directory: $SCRIPT_DIR"

        echo "  Claude agent complete."
        echo "=== Done $(date) ==="
        ;;
    snapshot)
        $PYTHON "$SCRIPT_DIR/pocketdev.py" snapshot --output "$SCRIPT_DIR/_snapshot.json"
        ;;
    audit)
        if [ -n "$TOOL" ]; then
            $PYTHON "$SCRIPT_DIR/pocketdev.py" audit --tool "$TOOL" --output "$SCRIPT_DIR/_last-audit.md"
        else
            $PYTHON "$SCRIPT_DIR/pocketdev.py" audit --output "$SCRIPT_DIR/_last-audit.md"
        fi
        ;;
    review)
        if [ -z "$TOOL" ]; then
            echo "ERROR: review requires a tool name."
            exit 1
        fi
        $PYTHON "$SCRIPT_DIR/pocketdev.py" review "$TOOL" --output "$SCRIPT_DIR/_last-review.md"
        ;;
    diagnose)
        if [ -z "$TOOL" ]; then
            echo "ERROR: diagnose requires a tool name."
            exit 1
        fi
        $PYTHON "$SCRIPT_DIR/pocketdev.py" diagnose "$TOOL" --output "$SCRIPT_DIR/_last-diagnose.md"
        ;;
    *)
        echo "Unknown mode: $MODE. Use: agent, snapshot, audit, review, diagnose"
        exit 1
        ;;
esac
```

- [ ] **Step 2: Commit**

```bash
git add run-pocketdev.sh
git commit -m "feat: rewrite shell wrapper with agent mode for daily Claude runs"
```

---

### Task 4: Seed the changelog with today's work

**Files:**
- Create: `_changelog.md`

- [ ] **Step 1: Write initial changelog**

Write `_changelog.md` with entries for all the work done today. This gives the Claude agent full context from day one.

Content should cover (in reverse chronological order):
- pocketDEV v3 rewrite (this task)
- pocketDEV v2 security enhancements (PII scan, secret scan, history scan, test execution)
- Finance history rewrite (PII purge)
- Skool hardcoded paths fix + Output/ untracked
- Claude Codex path sanitization
- UsageBOT redesign (black/white/teal), refactor, tests
- Backup System v2 (refactor, tests, username bug, digest cap)
- Git Sync separation from Backup System
- Transcriptor v2 history rewrite
- All .gitignore additions across repos
- pocketDEV v2 creation (3 modes: audit, review, diagnose)

Each entry: what changed, why, impact, decision context.

- [ ] **Step 2: Commit**

```bash
git add _changelog.md
git commit -m "feat: seed changelog with full history of today's work"
```

---

### Task 5: Create the initial backlog

**Files:**
- Create: `_backlog.md`

- [ ] **Step 1: Write initial backlog**

Run `python pocketdev.py snapshot --output _snapshot.json` first. Then read the snapshot and the actual source code of the key repos to produce an initial set of real improvement proposals. Include at least 2-3 proposals per actively-used tool (Finance, Backup System, Transcriptor, UsageBOT, Skool, pocketDEV itself).

Format per the spec:

```markdown
# pocketDEV Improvement Backlog
Last updated: 2026-04-04

## [Tool Name]

### [NEW] Title
**Impact:** High/Medium/Low | **Effort:** estimate
**What:** Specific change with file paths
**Why:** Problem it solves
**Added:** 2026-04-04
```

This is the first real output of pocketDEV-as-senior-dev. Make it count — read the code, find real improvements.

- [ ] **Step 2: Commit**

```bash
git add _backlog.md
git commit -m "feat: initial improvement backlog from first pocketDEV analysis"
```

---

### Task 6: Update CLAUDE.md and SessionStart integration

**Files:**
- Modify: `CLAUDE.md` — update to reflect v3 identity and workflows

- [ ] **Step 1: Rewrite CLAUDE.md**

Update the project CLAUDE.md to reflect v3:

```markdown
# pocketDEV — System Instructions

You are **pocketDEV**, a senior developer hired to maintain, improve, and evolve a portfolio of tools. You are not a linter. You are not an assistant. You are a peer engineer who reads code, understands architecture, and ships improvements.

## Your Knowledge Base

Every session, you have access to:
- `_changelog.md` — Full history of every change, with reasoning and decision context
- `_backlog.md` — Accumulated improvement proposals (new, approved, done, rejected)
- `_snapshot.json` — Latest structured data on all repos (generated daily at 22:00)

Read these before proposing anything. Your value comes from building on past work, not repeating it.

## How You Operate

### When the user says "review improvements"
1. Read `_backlog.md`
2. Present all `[NEW]` entries, grouped by tool, ranked by impact
3. For each: state the problem, the fix, the effort
4. Ask which to approve

### When the user says "review urgent"
1. Read `_urgent.md`
2. Present findings by severity
3. Propose immediate fixes

### When the user approves a backlog item
1. Mark it `[APPROVED]` → `[IN PROGRESS]` in `_backlog.md`
2. Implement the change
3. Run tests to verify
4. Mark `[DONE]` in `_backlog.md`
5. Write a changelog entry to `_changelog.md` with: what, why, impact, decision context

### When the user says "improve <tool>"
1. Read the tool's source code (not just the snapshot)
2. Read `_changelog.md` for past work on this tool
3. Read `_backlog.md` for existing proposals
4. Think deeply: architecture, features, efficiency, reliability, tests
5. Propose new improvements or update existing backlog entries
6. Wait for approval before implementing

### Audit / Review / Diagnose modes
These still work as before via `python pocketdev.py {audit,review,diagnose}`.

## Communication Style

- Direct, clinical, structured. No filler.
- When something is well-built, say so briefly.
- When something needs work, say what and why. File paths. Line numbers.
- Cap proposals at top 5 unless asked for more.
- Effort estimates are honest: quick fix (minutes), small project (hours), big project (days).

## Rules

1. **Never implement without approval.** Propose. Wait.
2. **Never delete files from disk** unless explicitly asked.
3. **Always update _backlog.md and _changelog.md** after implementing changes.
4. **Check the changelog before proposing.** Don't repeat solved work.
5. **Prioritize by blast radius.** Security > correctness > architecture > features > style.
6. **Ship clean.** Every commit leaves the repo better than you found it.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "feat: rewrite CLAUDE.md for pocketDEV v3 — Claude-powered senior developer"
```

---

### Task 7: Update .gitignore and clean up old files

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Update .gitignore**

Ensure these are all covered:

```
_last-audit.md
_last-review.md
_last-diagnose.md
_snapshot.json
_audit-pending
_audit.log
_pocketdev.log
_urgent.md
__pycache__/
*.pyc
venv/
.venv/
.env
*.log
dist/
build/
*.egg-info/

# OS files
.DS_Store
Thumbs.db
desktop.ini
```

Note: `_backlog.md` and `_changelog.md` are NOT gitignored — they're persistent and tracked.

- [ ] **Step 2: Remove old _audit-pending flag file**

```bash
rm -f _audit-pending
```

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: update gitignore for v3 files"
```

---

### Task 8: Set up Windows Task Scheduler for daily 22:00

- [ ] **Step 1: Create the scheduled task**

Run in PowerShell (elevated):

```powershell
$action = New-ScheduledTaskAction -Execute 'C:\Program Files\Git\usr\bin\bash.exe' -Argument '"C:\Users\Gaming PC\Desktop\Claude\Tool Auditor\run-pocketdev.sh" agent'
$trigger = New-ScheduledTaskTrigger -Daily -At '10:00PM'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun
Register-ScheduledTask -TaskName 'pocketDEV Daily' -Action $action -Trigger $trigger -Settings $settings
```

- [ ] **Step 2: Verify the task exists**

```powershell
Get-ScheduledTask -TaskName 'pocketDEV Daily' | Format-List TaskName,State,Triggers
```

- [ ] **Step 3: Test it manually**

```bash
./run-pocketdev.sh agent
```

Verify that `_snapshot.json` is created and `_backlog.md` is updated.

---

### Task 9: Update tool registry and README

**Files:**
- Modify: `README.md` — update for v3
- Modify: tool registry in memory system

- [ ] **Step 1: Update tool registry**

Change pocketDEV entry from v2.0 to v3.0 in the tool registry memory file.

- [ ] **Step 2: Update README.md**

Update the README to reflect v3: Claude-powered agent, daily runs, backlog system, changelog. Keep the existing mode documentation (audit/review/diagnose) and add the new agent mode and workflow.

- [ ] **Step 3: Final commit**

```bash
git add README.md
git commit -m "feat: pocketDEV v3.0 — Claude-powered senior developer with daily improvement runs"
```

---

### Task 10: End-to-end verification

- [ ] **Step 1: Run snapshot and verify JSON**

```bash
python pocketdev.py snapshot --output _snapshot.json
python -c "import json; d=json.load(open('_snapshot.json')); print(f\"Repos: {d['summary']['total_repos']}, LOC: {d['summary']['total_loc']}\")"
```

- [ ] **Step 2: Run the full agent mode**

```bash
./run-pocketdev.sh agent
```

Check that:
- `_snapshot.json` exists and has data
- `_backlog.md` was updated with `[NEW]` entries
- No `_urgent.md` was created (all repos should be clean)
- `_pocketdev.log` shows both phases completing

- [ ] **Step 3: Test the interactive workflow**

Start a new Claude Code session in the Tool Auditor directory. Verify:
- Claude reads `_backlog.md` and `_changelog.md`
- "review improvements" surfaces the proposals
- Approving an item leads to implementation + changelog update
