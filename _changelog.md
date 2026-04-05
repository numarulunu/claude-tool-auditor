# pocketDEV Changelog

Narrative log of every change made to the tool portfolio, with reasoning and decision context.
Reverse chronological order. One entry per logical change.

## 2026-04-05 — PFA Contabilitate: Claude Verification + Auto-updater + Folder Picker
**What changed:** Added "Verifica" button that sends calculation results + legislation + tax strategies to Claude for cross-checking. Added auto-updater (electron-updater). Added first-run folder picker so users choose their data directory. Fixed Python bundling (extraResources not files). Fixed claude CLI path resolution for packaged apps. Fixed stdin piping (execFile + stdin.write instead of shell redirect). Switched to one-click NSIS installer. Removed duplicate Import button. Released v1.0.1 through v1.2.5.
**Why:** User wants a pocket accountant, not just a calculator. The verification found a real error (amortization_threshold 2500 should be 5000 for 2026+ purchases per OUG 8/2026) and 13 unused tax strategies worth ~12,900 RON/year.
**Impact:** Claude now actively audits tax calculations against legislation. First step toward autonomous accountant.
**Decision context:** User vision: "I want it 100x better than an average accountant and 1000x faster. A pocket accountant that reads the law, organizes documents, fills declarations, and keeps everything current."

## 2026-04-05 — Claude HUD: Metin2 Grind + Dev Ranks + Audio Controls
**What changed:** Complete gamification rewrite. Dev-themed ranks (Script Kiddie → Machine Whisperer). Metin2 grind curve (300*n^3). XP heavily nerfed (tokens 100x nerf). New XP sources: project count, code deletion, subagent spawns. Dev-themed achievements. Start muted by default. Mute checkbox + volume slider. Window height 560→640. Hot-patching via asar extract instead of reinstalling.
**Why:** User was level 44 after one week — way too fast. Wanted developer-themed naming and grindier progression.
**Impact:** Level dropped from 44 to ~8. Senior Dev now takes 4 months instead of 1 week. Dev naming throughout.
**Decision context:** User referenced Metin2 (Korean MMO known for brutal leveling). "A week is nothing bruv."

## 2026-04-05 — Electron Lessons Learned (13 items)
**What changed:** Added comprehensive "Electron App Lessons" section to design_principles.md covering: preload.js in files list, executables in extraResources, artifact naming with dashes, private repo blocking, quitAndInstall flags, isQuitting pattern, gh upload verification, PATH resolution, stdin piping, data folder strategy, contextIsolation, hot-patching via asar extract, Windows exec gotchas. Plus release checklist.
**Why:** Every one of these was a bug encountered and fixed during Claude HUD and PFA Contabilitate development.
**Impact:** Future Electron apps won't repeat these mistakes.
**Decision context:** User said "Write those down so you won't make the same mistakes."

## 2026-04-05 — pocketDEV: Electron release pipeline + auto-updater check
**What changed:** Added `release` subcommand that automates: version bump → build → commit → push → GitHub Release → upload with verification + retry. Added audit check that flags Electron apps missing electron-updater. Fixed upload verification (was checking wrong filename). Fixed large file upload (separate from gh release create).
**Why:** Manual release process was error-prone. User wanted one-command releases.
**Impact:** `python pocketdev.py release "UsageBOT" --bump patch` does everything. Auto-updater delivers to users.

## 2026-04-04 — Transcriptor v2: Test suite (98 tests)
**What changed:** Created 5 test files covering 6 source modules: config loading (20 tests), process_v2 dispatch/retry/paths (34 tests), document processor (11 tests), processing calculator (21 tests), quiet mode (12 tests). All GPU/whisper dependencies fully mocked.
**Why:** Most complex tool in portfolio had zero tests. GPU retry, multi-threading, file dispatch, and diarization recovery were all untested.
**Impact:** 98 tests passing in 0.8s. Core logic now has regression protection without needing GPU hardware.
**Decision context:** pocketDEV operational assessment flagged this as the most dangerous gap. 4-6 hour estimate, done in one agent dispatch.

## 2026-04-04 — pocketDEV: Parallel snapshot + backlog CLI + git cache
**What changed:** snapshot_all() now uses ThreadPoolExecutor (4 workers) — 14.5s→6.5s (2.2x). New `backlog list` and `backlog stats` subcommands parse _backlog.md. Git subprocess results cached for 60s across modes.
**Why:** Snapshot was bottlenecked by sequential git commands. Backlog needed CLI access for automation. Git commands were duplicated across modes.
**Impact:** Snapshot viable as pre-conversation hook. Backlog queryable from scripts.
**Decision context:** Final 3 pocketDEV self-improvement backlog items, all low-medium effort.

## 2026-04-04 — Backup System: Digest deduplication + token counts
**What changed:** Added .last_sync mechanism — projects with no new JSONL data are skipped on daily runs. Added --force flag to bypass. Digests now include per-session and project-level token counts (input/output) extracted from the usage field in assistant messages. 13 new tests, 41/41 passing.
**Why:** Daily digest rebuilt all projects even when most were unchanged. Token counts let the memory sync protocol prioritize heavy sessions over lightweight ones.
**Impact:** Daily backup faster (skips unchanged projects). Digest metadata richer.
**Decision context:** Final 2 Backup System backlog items.

## 2026-04-04 — Finance: Add dry-run mode
**What changed:** Added `--dry-run` flag to contabilitate.py. Runs full pipeline (parse, calculate, reconcile) but skips all file writes. Summary still prints to terminal.
**Why:** Every run overwrites 8+ Excel files. During the year you often want to check tax position without regenerating all output.
**Impact:** Can query financial state without side effects. 42 tests passing.
**Decision context:** pocketDEV backlog item. Medium impact, 1 hour effort.

## 2026-04-04 — Transcriptor v2: Extract diarize recovery + simplify retry
**What changed:** Extracted 78-line inline diarize recovery block into standalone `run_diarize_pass()` function. Extracted file-type dispatch into `_dispatch_file()` method, collapsing 60-line manual retry block to 15 lines.
**Why:** Duplicated diarization logic meant bugs fixed in one path wouldn't be fixed in the other. Retry block duplicated dispatch logic — adding a new file type required changes in three places.
**Impact:** Single source of truth for both diarization and file dispatch. Adding new file types now requires one change instead of three.
**Decision context:** pocketDEV backlog items. High + Medium impact.

## 2026-04-04 — UsageBOT: Model tier detection + date filtering
**What changed:** Extended classifyModel() with regex patterns for versioned model names (opus-4, sonnet-4 etc.). Added unknownModels field to output JSON. Added --since/--until CLI flags that skip JSONL files by mtime.
**Why:** New model releases would silently get zero cost attribution. Full parse of all history takes 10+ seconds and growing. --since cuts this to under 1 second for daily refreshes.
**Impact:** Future-proof model detection. Incremental parsing viable. 46 tests passing.
**Decision context:** pocketDEV backlog items. Medium impact each.

## 2026-04-04 — Skool: JSON output validation and repair
**What changed:** Added JSON repair step in extract.py — when json.loads() fails, attempts to close unclosed brackets/braces and re-parse. Added validation of 8 expected top-level keys. Logs warnings for repairs and missing keys.
**Why:** Claude sometimes returns truncated JSON near the output token limit. Previously this was a permanent failure losing all valid content. Repair step salvages partial results.
**Impact:** Batch extractions recover from truncated responses automatically.
**Decision context:** pocketDEV backlog item. Medium impact, 30 min effort.

## 2026-04-04 — Preply Messenger: Retry with backoff on sends
**What changed:** Wrapped message send operation in messenger.js with retry loop: 3 attempts at 5s/10s/20s delays. Each failure logged via structured logger with attempt number and backoff duration.
**Why:** Network blips or Preply UI changes cause transient failures. Previously permanent, requiring manual re-run.
**Impact:** Transient send failures handled automatically. Structured log trail for debugging.
**Decision context:** pocketDEV operational assessment. Medium impact, 1 hour effort.

## 2026-04-04 — Finance: Extract main() into pipeline stages
**What changed:** Split 596-line main() in contabilitate.py into 5 named functions: parse_bank_statements(), process_income_sources(), process_expenses(), generate_outputs(), print_summary(). main() is now a ~50-line orchestrator. Also fixed mutable state bug where fitness_ytd was stored on the function object itself — replaced with local variable.
**Why:** Untestable monolith. Each income source followed the same pattern but was inlined. Adding new income sources (Skool, direct invoices) meant touching a 600-line function. The function-object state was a bug waiting to happen if main() ever ran twice.
**Impact:** Each stage independently testable. 42 tests still passing. Code went from 1 god-function to 5 focused stages with clear data flow.
**Decision context:** Highest-impact backlog item. The 596-line main() was flagged in every pocketDEV review.

## 2026-04-04 — Transcriptor v2: Structured logging
**What changed:** Added logging module across 8 files, 62 logging points. Smart routing: quiet_print() uses a file-only logger (no double console output), direct logger calls go to both file and stream. CLI UI output (progress bars, spinners) stays as print().
**Why:** 88 print() calls vanishing when run from Task Scheduler. Most complex tool in portfolio with GPU retry logic, multi-threading, diarization — needs persistent logs for debugging.
**Impact:** All processing steps now logged to backend/transcriptor.log with timestamps and severity.
**Decision context:** pocketDEV operational assessment flagged Transcriptor as highest-risk for silent failures after Finance.

## 2026-04-04 — UsageBOT: Safe data embedding
**What changed:** Replaced fragile HTML mutation (lastIndexOf + regex rewriting of index.html) with a separate usage-data.js file. Parser writes data to usage-data.js, index.html loads it via script tag. index.html shrunk from 986KB to 31KB.
**Why:** The regex on the old approach was greedy and had corrupted index.html during development. String-replacing inside HTML by finding the last script tag is inherently fragile.
**Impact:** index.html is now stable across parser runs. 46 tests passing. Dashboard works identically.
**Decision context:** pocketDEV backlog item. High impact, 1 hour effort.

## 2026-04-04 — Backup System: Incremental conversation sync
**What changed:** Replaced `cp -ru` in backup.sh with Python-based sync-conversations.py. Only copies new/modified files (compares size + mtime). Reports errors individually instead of failing silently. Added 6 tests. Also added Python auto-detection to backup.sh.
**Why:** cp -ru copied the entire directory tree every time, failed silently on permission errors, and got slower as conversation data grew.
**Impact:** Incremental sync — skips unchanged files. Errors are visible. 28/28 tests passing.
**Decision context:** pocketDEV backlog item. The cp -ru failure mode was discovered during the Backup System deep review.

## 2026-04-04 — Chat Widget: Error handling overhaul
**What changed:** Fixed 2 empty `catch {}` blocks in vocality-chat.js. Added 10-second timeout and 1-retry with 2s delay on the n8n webhook call. All errors now log with `[VocalityChat]` prefix.
**Why:** Empty catch blocks were silently swallowing all errors. Users saw a dead widget with no feedback. Webhook had no timeout — a hung request blocked the UI indefinitely.
**Impact:** Errors are now visible in console. Webhook failures show user-facing fallback (WhatsApp link). Transient network failures handled by retry.
**Decision context:** pocketDEV operational maturity assessment identified Chat Widget as the most operationally naked repo in the portfolio.

## 2026-04-04 — Finance: Structured logging
**What changed:** Replaced 39 `print()` calls in contabilitate.py with Python `logging` module. 32 info, 7 warning. Log file writes to `contabilitate.log` with timestamps. Final summary output kept as print() for interactive use.
**Why:** When run from Task Scheduler, print() output vanishes. This tool processes real financial data — silent failures cost real money.
**Impact:** All processing steps now logged with timestamps and severity. 42 tests still passing.
**Decision context:** pocketDEV operational assessment flagged Finance and Transcriptor as the two highest-risk tools for silent failures.

## 2026-04-04 — Claude Codex: React error boundary
**What changed:** Added ErrorBoundary component wrapping the root App tree. Catches render crashes, shows recovery UI with "Try Again" button, logs to console.error.
**Why:** No error boundary meant one bad render in any component = white screen with no recovery.
**Impact:** App now survives render crashes gracefully.
**Decision context:** pocketDEV operational assessment. Low effort (20 min), medium impact.

## 2026-04-04 — Skool: Exponential backoff retry
**What changed:** Wrapped Claude CLI subprocess call in extract.py with retry loop: 3 attempts at 30s/60s/120s delays. Distinguishes rate limits, timeouts, and permanent errors.
**Why:** Parallel extraction (--parallel 3-4) hits rate limits. Previously recorded as permanent failures requiring manual --retry-failed. Now handles transient failures automatically.
**Impact:** Batch extractions can complete without manual intervention on rate limits.
**Decision context:** pocketDEV backlog item + operational assessment. Skool's extraction pipeline is the primary consumer of Claude API calls.

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
