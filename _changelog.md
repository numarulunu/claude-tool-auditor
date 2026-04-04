# pocketDEV Changelog

Narrative log of every change made to the tool portfolio, with reasoning and decision context.
Reverse chronological order. One entry per logical change.

---

## 2026-04-04

### pocketDEV v3 — snapshot subcommand + agent prompt + shell wrapper
- **What changed:** Added `snapshot` subcommand that writes `_snapshot.json` (repo health summary for LLM consumption). Created `agent-prompt.md` (instructions for Claude-powered daily runs). Created `run-pocketdev.sh` shell wrapper for scheduled execution.
- **Why:** pocketDEV needed a machine-readable output mode so Claude sessions can consume audit results without re-running scans. The shell wrapper enables cron-style automated health checks.
- **Impact:** Enables daily automated portfolio health monitoring via Claude scheduled agents.
- **Decision context:** Part of the v3 plan to make pocketDEV agent-native rather than human-only.

### pocketDEV v2 — security enhancements
- **What changed:** Added PII detection (email, phone, user paths), secret scanning (API keys, private keys, connection strings, JWT), git history scanning for previously committed sensitive files, test execution in audit mode. Issues now categorized as critical/warning/info.
- **Why:** The portfolio had real PII and secrets scattered across repos (discovered during finance history rewrite). Needed automated detection to prevent future leaks.
- **Impact:** Every audit now surfaces security issues ranked by severity. Catches problems before they reach GitHub.
- **Decision context:** Triggered by finding bank statements and IBANs committed to the finance repo. Prevention over cleanup.

### Finance repo — history rewrite
- **What changed:** Fresh `git init`, purged 331 personal financial files from history (bank statements, invoices, contracts, Stripe client emails, IBAN RO12 RZBR...). Replaced test email with `test@example.com`. Repo went from 390 to 59 tracked files.
- **Why:** The repo contained highly sensitive personal financial data committed over time. A `.gitignore` fix alone wouldn't purge history.
- **Impact:** Repo is now safe to push to GitHub. History is clean. No recoverable PII.
- **Decision context:** Chose fresh init over `git filter-repo` because the old history had no value worth preserving — it was all file additions with no meaningful commit narrative.

### Skool — path fixes + output cleanup
- **What changed:** Replaced hardcoded `C:\Users\Gaming PC` paths with `Path(__file__).parent` in `extract.py`. Untracked 420 `Output/` files (generated scripts with student names, local paths). Removed `parallel.txt` scratch notes.
- **Why:** Hardcoded paths break portability. Output files contained student PII (names in filenames) and should never have been tracked.
- **Impact:** Tool is now portable. No student data in git history.
- **Decision context:** Output files are generated artifacts — they belong in `.gitignore`, not the repo.

### Claude Codex — path sanitization
- **What changed:** Sanitized `/Users/Gaming` home directory path in design doc.
- **Why:** Personal path leaked into a document that could be shared or published.
- **Impact:** Minor. One path reference removed.
- **Decision context:** Found during the broader PII sweep across all repos.

### UsageBOT — redesign + refactor + tests
- **What changed:** Rewrote dashboard from dark-themed monospace to black bg / white cards / teal accent per brand spec. Refactored `parse-claude-data.js`: extracted `aggregateSessions()`, `calculateCosts()`, `buildProjectList()`, `calcCost()`, `generateDashboardHtml()`. Added `--quiet` flag, `require.main` guard, module exports. Added 46 tests. Added avg tokens/session card + sub-agent spawns metric. Dated cost rates.
- **Why:** Dashboard looked like a terminal dump. Needed to match Vocality brand standards (black/white/teal). Code was a single monolithic function — untestable.
- **Impact:** Dashboard is now presentable. Code is modular and tested. Cost calculations account for rate changes over time.
- **Decision context:** UsageBOT is the tool most likely to be shown to others (usage stats). Brand alignment matters here.

### Backup System v2 — refactor + tests + separation
- **What changed:** Refactored `memory-sync.py`: extracted `run()` into `write_manifest()`, `write_pending_flag()`, `extract_project()`, `extract_content_text()`. Fixed username parsing bug for multi-word usernames (Gaming PC -> GAMING-1). Added 5MB digest size cap. Added error recovery + `_backup-failed` flag to `backup.sh`. Syncs all memory directories (not just first). Removed unused `defaultdict` import. Added 22 tests. Removed `config.json` (unused). Removed `backup-all-tools.sh` (separated into Git Sync).
- **Why:** `memory-sync.py` was a single function doing everything. The username bug caused backup failures on this machine. Git push logic didn't belong in the backup system.
- **Impact:** Backups are reliable, testable, and separated from git operations. Username edge case fixed.
- **Decision context:** The git-push responsibility was pulled out into its own project (Git Sync) because it serves a different purpose and has different failure modes.

### Git Sync v1.0 — new project
- **What changed:** New project separated from Backup System. Auto-discovers and pushes all git repos. Added `--dry-run` flag with file-level logging. Created GitHub repo `numarulunu/git-sync`.
- **Why:** Git pushing was bolted onto the backup system but is a distinct concern. It needs its own error handling, logging, and dry-run capability.
- **Impact:** Clean separation of concerns. Backup handles memory sync; Git Sync handles repo pushing.
- **Decision context:** Separated rather than duplicated. Backup System no longer touches git push.

### Transcriptor v2 — history rewrite
- **What changed:** Fresh `git init`, purged ~115GB of lesson recordings and `.venv` from history. 17 code files tracked.
- **Why:** Binary lesson recordings (audio/video) were committed to git, bloating the repo to an absurd size. `.venv` was also tracked.
- **Impact:** Repo is now a normal size. Only source code is tracked.
- **Decision context:** Same approach as Finance — fresh init because the old history was pure noise.

### .gitignore additions across repos
- **What changed:** Transcriptor (`Material/`, `.venv/`, `*.mp4`, `*.dll` etc.), Backup System (`_digests/*.md`), Chat Widget (`node_modules/`, `dist/`, `.env`). Added `_digests` and `_conversations` to pocketDEV's `SKIP_DIRS`.
- **Why:** Each repo had generated or sensitive files that should have been ignored from the start.
- **Impact:** Future commits won't accidentally include binaries, dependencies, or generated digests.
- **Decision context:** Preventive. Applied during the security sweep rather than waiting for the next incident.

### pocketDEV v2 — creation (renamed from Tool Auditor)
- **What changed:** Renamed project from Tool Auditor to pocketDEV. Three modes: audit, review, diagnose. Auto-discovers repos including nested repos. Fixed GitHub slug parsing (`rstrip` bug). Large-file check now only flags git-tracked files. Excluded `claude-backup` meta repo.
- **Why:** Tool Auditor was a single-purpose scanner. pocketDEV is the broader vision — a developer peer that maintains the whole portfolio.
- **Impact:** Single entry point for all repo maintenance. Auto-discovery means new repos are picked up without config changes.
- **Decision context:** The `rstrip` bug was silently corrupting GitHub URLs. The large-file false positives were noise — only tracked files matter.

### Repo cleanup — misc
- **What changed:** Added LICENSE to Git Sync, `requirements.txt` to Shelf, `package-lock.json` to UsageBOT.
- **Why:** Standard repo hygiene. Missing lock files cause dependency drift. Missing licenses are a legal gap.
- **Impact:** Minor. Repos now have expected standard files.
- **Decision context:** Opportunistic cleanup during the audit sweep.

### GitHub repo created — git-sync
- **What changed:** Created `numarulunu/git-sync` on GitHub.
- **Why:** Git Sync needed a remote to be backed up and versioned.
- **Impact:** Repo is now pushed and available remotely.
- **Decision context:** Part of the Git Sync v1.0 launch.
