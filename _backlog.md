# pocketDEV Improvement Backlog
Last updated: 2026-04-04

## Transcriptor v2

### [DONE] Fix thread safety: _diarize_total and progress_bar unprotected across threads
**Impact:** High | **Effort:** Quick fix (30 minutes)
**What:** `process_v2.py:464,597,704` — `self._diarize_total` is incremented from multiple worker threads without any lock. `self.progress_bar.update()` is called from multiple threads at lines 441, 467, 473, 480 without synchronization. Add `_diarize_total_lock` and `_progress_lock` to `__init__()` and wrap all access points.
**Why:** Data race on a live counter. `_diarize_total` is read at line 554 for display while workers increment it — value can be torn on non-atomic int operations. Progress bar corruption causes garbled terminal output during multi-file processing.
**Added:** 2026-04-04

### [DONE] Extract process_all() (271 lines) into 3 pipeline phases
**Impact:** High | **Effort:** Small project (3-4 hours)
**What:** `process_v2.py:483-753` is a 271-line god function doing setup/filtering (483-510), whisper init + task dispatch (511-660), and retry + diarization drain (661-751). Extract into `_prepare_materials()`, `_run_primary_processing()`, `_run_diarization_drain()`. The nested `_diarize_worker()` closure at line 569 should become a method.
**Why:** Untestable monolith. Each phase has distinct responsibilities and failure modes (GPU init vs. thread coordination vs. diarization). Extracting phases enables targeted tests and makes resume/checkpoint logic feasible.
**Added:** 2026-04-04

### [DONE] Log futures exceptions instead of silently swallowing them
**Impact:** High | **Effort:** Quick fix (15 minutes)
**What:** `process_v2.py:649-650` — `except Exception: pass` silently drops all worker thread exceptions including GPU OOM, CUDA crashes, and file corruption. Replace with `logger.error("Worker exception: %s", e)` and increment `self.stats['errors']`. Same pattern at lines 728-729 (diarizer GPU move) and 910 (diarize recovery).
**Why:** GPU crashes and OOM errors are invisible. When processing fails on a file, the only evidence is a missing output — no log entry, no error count, no stack trace. Debugging production failures requires re-running with print statements.
**Added:** 2026-04-04

## pocketDEV

### [DONE] Add test suite for core scanning functions
**Impact:** High | **Effort:** Small project (4-6 hours)
**What:** `pocketdev.py` has zero tests despite being the most active repo (20 commits/30d) and the longest file (1672 lines). Priority targets: (1) `scan_secrets()` lines 444-482 — mock files with known patterns, verify detection, (2) `scan_pii()` lines 485-548 — verify false-positive filtering, (3) `find_issues()` lines 351-441 — integration of all scans, (4) `parse_backlog()` lines 1452-1480 — parse known markdown structures, (5) `snapshot_repo()` lines 1235-1399 — mock git commands, verify JSON structure.
**Why:** Every scan improvement risks breaking existing detection. The PII false-positive filters (lines 534-537) and secret patterns (line 57) are regex-heavy and need regression protection. Backlog parsing is used by automation and has no validation.
**Added:** 2026-04-04

### [DONE] Extract shared scanning into a RepositoryScanner class
**Impact:** High | **Effort:** Small project (3-4 hours)
**What:** `scan_secrets()`, `scan_pii()`, `scan_history()`, `detect_tests()`, `run_tests()`, `check_dependencies()` are called independently from `audit_repo()` (lines 313-314), `review_repo()` (lines 800-846), `snapshot_repo()` (lines 1317-1360), and `diagnose_repo()` (lines 1070-1084). Each mode re-reads tracked files and re-runs git commands. Consolidate into a `RepositoryScanner` class that reads files once, runs all scans in a single pass, and exposes results as a dict. All four modes call `scanner.scan_all()` instead of individual functions.
**Why:** ~200 lines of duplication across modes. Adding a new scan (e.g., license compliance) requires changes in 4 places. Single-pass scanning would be 3x faster (one file read instead of three).
**Added:** 2026-04-04

### [DONE] Extract snapshot_repo() (165 lines) into composable sub-functions
**Impact:** Medium | **Effort:** Small project (2-3 hours)
**What:** `pocketdev.py:1235-1399` is the largest function in the file. It collects git info (1252-1284), file stats (1285-1316), test results (1317-1325), security data (1328-1351), dependencies (1354-1360), and structure (1363-1399). Extract into `_snapshot_git_info()`, `_snapshot_files()`, `_snapshot_tests()`, `_snapshot_security()`, `_snapshot_dependencies()`, `_snapshot_structure()`. Orchestrator becomes ~30 lines assembling a dict.
**Why:** Each sub-function is independently testable. The git info collection (12 subprocess calls) is the main performance bottleneck — isolating it enables targeted caching. Currently, any change to the snapshot format risks breaking unrelated sections.
**Added:** 2026-04-04

## UsageBOT

### [DONE] Commit 5 uncommitted files (start.bat, test.js, and 3 modified)
**Impact:** Medium | **Effort:** Quick fix (5 minutes)
**What:** `git status` shows 5 uncommitted files: `start.bat` (new), `test.js` (new, 46-test suite), `README.md` (modified), `package.json` (modified — added test/parse:quiet scripts), `serve.js` (modified — added /api/refresh endpoint). These are completed features from the last improvement cycle sitting uncommitted.
**Why:** Uncommitted work is unversioned and unrecoverable if the machine fails. The test suite (`test.js`) is the most critical — losing it means re-writing 46 tests.
**Added:** 2026-04-04

### [DONE] Fix Set serialization in JSON output — allFiles lost on stringify
**Impact:** Medium | **Effort:** Quick fix (15 minutes)
**What:** `parse-claude-data.js:360` — `allFiles` is stored as a JavaScript `Set`. When the output object is passed to `JSON.stringify()` at line 638, Sets serialize to `{}` (empty object), silently losing all file tracking data. Convert `allFiles` to `Array.from(allFiles)` before JSON serialization, or use an Array throughout.
**Why:** Any downstream consumer reading `usage-stats.json` gets an empty object for `allFiles` instead of the actual file list. The data is collected correctly but discarded at write time.
**Added:** 2026-04-04

## Skool

### [DONE] Extract extract_transcript() (154 lines) into focused functions
**Impact:** Medium | **Effort:** Small project (2 hours)
**What:** `extract.py:244-398` handles 4 distinct responsibilities: temp file creation (270-274), subprocess execution with backoff (276-318), JSON extraction and repair (322-363), and key validation (373-390). Extract into `_build_prompt_file()`, `_call_claude_cli()`, `_parse_and_repair_json()`, `_validate_keys()`. The JSON repair logic (lines 336-357) is particularly complex bracket/quote matching that deserves its own function and tests.
**Why:** The JSON repair logic is brittle — it uses `rfind` to locate cut points in truncated responses. Isolating it makes targeted testing possible. Currently, testing any part of extraction requires mocking the entire Claude CLI subprocess chain.
**Added:** 2026-04-04

## Finance

### [DONE] Extract main() into a pipeline of named stages
**Impact:** High | **Effort:** 2-3 hours
**What:** `contabilitate.py:116-712` is a single 596-line `main()` function. Split into pipeline stages: `parse_bank_statements()` (lines 141-198), `process_income_sources()` (lines 199-320), `process_invoices()` (lines 321-495), `generate_outputs()` (lines 496-584), `print_summary()` (lines 586-712). Each stage returns a typed dataclass (e.g. `IncomeResult`, `ExpenseResult`) that feeds the next.
**Why:** A single function this long is untestable. Each income source (Preply, Stripe, RI invoices) follows the same pattern (parse -> convert FX -> create RJIP entries -> accumulate monthly totals) but the logic is inlined and repeated. Extracting stages makes each one independently testable and lets you add new income sources (Skool, direct invoices) without touching a 600-line function.
**Added:** 2026-04-04

### [DONE] Eliminate mutable state on function object for fitness cap tracking
**Impact:** Medium | **Effort:** 15 minutes
**What:** `contabilitate.py:400-401` uses `main._fitness_ytd` — a dict attached to the function object itself — to track year-to-date fitness deductions across loop iterations. Replace with a local variable initialized before the invoice loop at line 337 (e.g. `fitness_ytd_eur = 0.0`).
**Why:** Storing mutable state on a function object is a subtle bug vector. If `main()` is ever called twice in the same process (tests, multi-year runs), the state persists across calls. A local variable scoped to the loop is cleaner and correct.
**Added:** 2026-04-04

### [DONE] Add dry-run mode that shows calculated totals without writing files
**Impact:** Medium | **Effort:** 1 hour
**What:** Add `--dry-run` flag to `contabilitate.py`. When set, run the full pipeline (parse, calculate, reconcile) but skip all file writes in the generate_outputs stage (lines 496-584). Print the summary (lines 586-674) as normal.
**Why:** Right now, every run overwrites the Excel outputs. During the year you often want to check current tax position without regenerating all 8+ Excel files. A dry-run mode lets you query your financial state without side effects.
**Added:** 2026-04-04

## Backup System

### [DONE] Replace fragile cp -ru with rsync-style incremental sync
**Impact:** High | **Effort:** 1 hour
**What:** `backup.sh:86` uses `cp -ru "$PROJECTS_DIR/" "$CONV_DIR/"` to sync conversations. This fails silently on permission errors and copies the entire directory tree every time. Replace with `rsync -a --delete` (available in Git Bash on Windows via MSYS2) or rewrite the conversation sync as a Python script that does incremental copy based on mtime comparison.
**Why:** The current approach has failed silently in the past (the `log_warn` on line 89 catches the exit code but not partial failures). With conversation files growing over time, a proper incremental sync avoids copying gigabytes of unchanged JSONL files.
**Added:** 2026-04-04

### [DONE] Add digest deduplication — skip projects with no new conversations
**Impact:** Medium | **Effort:** 45 minutes
**What:** `memory-sync.py:290-340` iterates every project directory and rebuilds the full digest even when no new JSONL data exists since the last run. Add a `.last_sync` timestamp file per project. On each run, compare JSONL mtimes against `.last_sync` and skip projects with no changes. Only rebuild digests for projects with new conversation data.
**Why:** The daily digest currently regenerates all projects every time, which takes 5-10 seconds and produces identical output for inactive projects. With 11+ projects, most are unchanged on any given day. Skipping unchanged projects makes the daily backup faster and the manifest more meaningful (only listing projects with new data).
**Added:** 2026-04-04

### [DONE] Add conversation token/message counts to digest metadata
**Impact:** Low | **Effort:** 30 minutes
**What:** `memory-sync.py:173-202` builds digest headers with conversation count and date range but no token-level stats. Parse the `usage` field from assistant messages (already available in the JSONL) and add per-session token counts (input, output, cache) to each session header. Add total token count to the project header.
**Why:** The digest is consumed by the memory sync protocol, which needs to decide how much context to pull. Token counts let it prioritize heavy sessions (where real work happened) over lightweight ones (quick questions). Currently it has no signal for session weight.
**Added:** 2026-04-04

## Transcriptor v2

### [DONE] Extract diarize-only recovery path into a reusable function
**Impact:** High | **Effort:** 1.5 hours
**What:** `process_v2.py:856-934` contains a 78-line inline block that duplicates the diarization logic from `process_all()` (lines 558-576). The same pattern — load sidecar JSON, find media file, run diarizer, overwrite transcript — appears in both places with minor variations. Extract into a `DiarizeRecovery` class or a standalone `run_diarize_pass(output_dir, source_dir, config)` function that both code paths call.
**Why:** The duplicated diarization logic means bugs fixed in one path won't be fixed in the other. The recovery path at line 856 also has a nested loop searching for media files (lines 897-904) that is O(n*m) on directories — a correctness risk if filenames collide across subdirectories.
**Added:** 2026-04-04

### [DONE] Replace process_all() retry logic with a proper retry decorator
**Impact:** Medium | **Effort:** 1 hour
**What:** `process_v2.py:649-709` has a 60-line retry block that duplicates the per-file-type dispatch logic from `_process_file_wrapper()` (lines 410-430). The retry block manually checks `ft in ('audio', 'video')` and re-dispatches, then does the same for pdf/image/document. Use a retry wrapper (e.g. `tenacity` or a simple custom decorator) on `_process_file_wrapper` with `max_retries=1` and `wait_fixed=1`, eliminating the manual retry queue entirely.
**Why:** The retry block duplicates dispatch logic, which means adding a new file type requires changes in three places: `_process_file_wrapper`, the retry block, and `type_map`. A decorator-based retry collapses this to one place.
**Added:** 2026-04-04

## UsageBOT

### [DONE] Move data embedding from mutation to template injection
**Impact:** High | **Effort:** 1 hour
**What:** `parse-claude-data.js:598-610` embeds the usage stats JSON into `index.html` by string-replacing the last `<script>` tag. This is fragile: it uses `lastIndexOf('<script>')` and a regex replace to strip the previous embedded data. If the HTML structure changes (e.g. another script tag is added), this silently corrupts the file. Replace with a designated placeholder comment (e.g. `/* __USAGE_DATA__ */`) and do a targeted replacement, or better, write to a separate `usage-stats-embedded.js` file that `index.html` imports.
**Why:** The current approach has destroyed the index.html structure at least once during development (the regex on line 602 is greedy with `[\s\S]*?`). A separate data file eliminates the mutation risk entirely and makes the HTML stable across runs.
**Added:** 2026-04-04

### [DONE] Add cost tracking for new model tiers (Opus 4, extended thinking)
**Impact:** Medium | **Effort:** 30 minutes
**What:** `parse-claude-data.js:20-24` hardcodes cost rates for opus/sonnet/haiku. The `classifyModel()` function at line 29 only checks for these three strings. Add classification for `opus-4` (which may have different pricing), and add an `unknown` cost tier that defaults to sonnet pricing but flags sessions using unrecognized models in the output JSON.
**Why:** As Anthropic releases new models, sessions using them will silently get classified as "unknown" with zero cost attribution. The dashboard will undercount spending. A fallback rate + a warning field ensures cost estimates stay accurate even before the parser is updated.
**Added:** 2026-04-04

### [DONE] Add date range filtering to avoid re-parsing all history
**Impact:** Medium | **Effort:** 45 minutes
**What:** `parse-claude-data.js:417-527` parses every JSONL file in `~/.claude/projects/` on every run. Add `--since YYYY-MM-DD` and `--until YYYY-MM-DD` flags that skip JSONL files whose mtime falls outside the range. For incremental updates, add `--incremental` that reads the previous `usage-stats.json`, only parses files modified since `generatedAt`, and merges the new sessions.
**Why:** With months of accumulated conversation data, the full parse takes 10+ seconds and will only get slower. Most dashboard refreshes only need the last day's data. Incremental parsing would bring refresh time under 1 second.
**Added:** 2026-04-04

## Skool

### [DONE] Add structured retry with exponential backoff for Claude CLI calls
**Impact:** High | **Effort:** 45 minutes
**What:** `extract.py:277-284` shells out to `claude --print` with a 5-minute timeout but no retry logic for transient failures (rate limits, network blips, Claude API overload). Add exponential backoff retry (3 attempts, 30s/60s/120s delays) around the `subprocess.run` call. Also capture and distinguish exit codes: timeout vs. rate-limit vs. actual error.
**Why:** The parallel extraction pipeline (`--parallel 3-4`) is likely to hit rate limits. Currently a rate-limited request is recorded as a permanent failure that requires `--retry-failed` to recover. Automatic backoff would let a batch run complete without manual intervention.
**Added:** 2026-04-04

### [DONE] Validate and repair JSON output before saving
**Impact:** Medium | **Effort:** 30 minutes
**What:** `extract.py:293-301` strips markdown fences and parses JSON, but Claude sometimes returns truncated JSON (especially for long transcripts near the output token limit). Add a JSON repair step: if `json.loads()` fails, try closing unclosed brackets/braces and re-parsing. Also validate that the parsed JSON contains the expected top-level keys (`metadata`, `technical_corrections`, etc.) and log a warning if any are missing.
**Why:** Currently a truncated JSON response from Claude causes the extraction to be marked as failed, losing all the valid content that was returned. A repair step salvages partial results. Key validation catches prompt drift (Claude changing the schema) early.
**Added:** 2026-04-04

## pocketDEV

### [DONE] Parallelize snapshot mode across repos
**Impact:** Medium | **Effort:** 45 minutes
**What:** `pocketdev.py:1366-1372` (`snapshot_all`) processes repos sequentially. Each repo runs 6+ git commands and reads all tracked files. Use `concurrent.futures.ThreadPoolExecutor` to snapshot repos in parallel (4-6 workers). The `snapshot_repo()` function is already stateless — it takes a repo dict and returns a snapshot dict — so parallelization is safe.
**Why:** With 11 repos, the sequential snapshot takes 15-20 seconds (mostly git subprocess overhead). Parallel execution would cut this to ~5 seconds, making the daily snapshot viable as a pre-conversation hook.
**Added:** 2026-04-04

### [DONE] Add `backlog` subcommand to manage this file programmatically
**Impact:** Medium | **Effort:** 1.5 hours
**What:** Add `pocketdev.py backlog list`, `backlog add --tool "X" --title "Y"`, `backlog resolve <id>`, `backlog stats` subcommands. Parse `_backlog.md` as structured data (regex on the existing heading/field format). `resolve` moves an item from `[NEW]` to `[DONE]` with a completion date. `stats` shows counts by tool and status.
**Why:** Currently the backlog is a manual markdown file. As it grows, finding open items, tracking completion, and preventing duplicates requires reading the whole file. A CLI interface makes the backlog actionable from automation (e.g. "show me open items for Finance" in a pre-session hook).
**Added:** 2026-04-04

### [DONE] Cache git data between audit/review/snapshot modes
**Impact:** Low | **Effort:** 30 minutes
**What:** `pocketdev.py` runs `git ls-files`, `git status --porcelain`, `git log` etc. independently in `audit_repo()`, `snapshot_repo()`, and `review_repo()`. If multiple modes are run in sequence (e.g. snapshot then audit), the same git commands run twice. Add a simple `GitCache` class that memoizes subprocess results by `(repo_dir, command_tuple)` with a 60-second TTL.
**Why:** Minor optimization, but it matters when running the full suite across 11 repos. Each repo currently runs 8-10 git commands per mode. Caching across modes would halve the subprocess count.
**Added:** 2026-04-04

## Cross-Portfolio — Operational Gaps

### [DONE] Add structured logging to Finance and Transcriptor v2
**Impact:** High | **Effort:** 1-2 hours each
**What:** Both tools use `print()` for all output. Replace with Python's `logging` module configured to write to a `.log` file with timestamps and severity levels. Finance: `contabilitate.py` has ~30 print calls. Transcriptor: `process_v2.py` has ~88 print calls. Configure `logging.basicConfig(filename='tool.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')` and replace print→logging calls.
**Why:** When run from Task Scheduler or background processes, `print()` output vanishes. These are the two tools where silent failures cost real money (Finance) or real time (Transcriptor). Structured logs with timestamps are essential for debugging scheduled runs.
**Added:** 2026-04-04

### [DONE] Add tests to Transcriptor v2
**Impact:** High | **Effort:** 4-6 hours
**What:** Zero test files exist for a tool with GPU retry logic (`_transcribe_with_retry`), multi-threaded processing, diarization recovery, and API endpoints. Priority test targets: (1) `_transcribe_with_retry` — mock whisper, verify retry on OOM, (2) file type dispatch in `_process_file_wrapper`, (3) diarization recovery path at `process_v2.py:856-934`, (4) API route handlers.
**Why:** Most complex tool in the portfolio with the highest failure surface area. GPU OOM recovery, file format detection, and multi-threading are all untested. A regression here means hours of re-processing.
**Added:** 2026-04-04

### [DONE] Fix Chat Widget empty catch blocks and add error handling
**Impact:** High | **Effort:** 30 minutes
**What:** `widget/vocality-chat.js` has empty `catch {}` blocks that silently swallow all errors. Replace with `catch (err) { console.error('Widget error:', err); }`. Add a 10-second timeout and basic retry (1 attempt) on the n8n webhook call. The widget currently has zero error feedback to the user — if the API fails, nothing happens.
**Why:** Actively hiding errors. Users get a dead chat widget with no indication anything went wrong. The n8n webhook has no timeout — a hung request blocks the UI indefinitely.
**Added:** 2026-04-04

### [DONE] Add React error boundary to Claude Codex
**Impact:** Medium | **Effort:** 20 minutes
**What:** No error boundary exists in the React app. A single uncaught render error crashes the entire app to a white screen. Add an `ErrorBoundary` component at the root (`src/App.jsx` or equivalent) that catches render errors and shows a fallback UI.
**Why:** React apps without error boundaries have zero crash resilience. One bad state in any component takes down everything.
**Added:** 2026-04-04

### [DONE] Add retry with backoff to Preply Messenger send operations
**Impact:** Medium | **Effort:** 1 hour
**What:** `src/messenger.js` sends messages via Playwright page interactions with no retry on failure. If a page navigation times out or an element selector fails, the message is lost. Add retry logic (3 attempts, 5s/10s/20s backoff) around the send operation. Log failures to `logs/activity.log` (structured logging already exists in this repo).
**Why:** Network blips or Preply UI changes cause transient failures. Currently these are permanent failures requiring manual re-run. Retry with backoff would handle the common case automatically.
**Added:** 2026-04-04
