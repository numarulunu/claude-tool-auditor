"""
pocketDEV — Your senior developer on call.
Audits, reviews, and diagnoses your git-tracked projects.

Modes:
    audit                        Health scan across all discovered repos
    review <tool>                Deep code quality dive into one tool
    diagnose <tool>              Gather diagnostic info when something's broken

Usage:
    python pocketdev.py audit                         # Scan all repos
    python pocketdev.py audit --tool "Finance"        # Filter by name
    python pocketdev.py review "Finance"              # Deep review one tool
    python pocketdev.py diagnose "Transcriptor"       # Diagnose a broken tool
    python pocketdev.py --scan-dir ~/Projects audit   # Custom scan directory
"""

import json
import os
import re
import subprocess
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

SKIP_DIRS = {".git", "node_modules", "__pycache__", "venv", ".venv", "dist",
             "build", ".next", ".nuxt", "coverage", ".tox", "egg-info"}

# Repos to skip during discovery (parent/meta repos that aren't standalone tools)
EXCLUDE_REPOS = {"claude-backup"}

BINARY_EXTS = {".exe", ".dll", ".so", ".dylib", ".lib", ".pyd", ".pyc",
               ".whl", ".tar", ".gz", ".zip", ".7z", ".rar",
               ".mp4", ".m4a", ".mp3", ".wav", ".flac", ".avi", ".mkv",
               ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".ico", ".svg",
               ".pdf", ".doc", ".docx", ".xls", ".xlsx",
               ".ttf", ".otf", ".woff", ".woff2", ".eot"}

SECRET_PATTERNS = [
    re.compile(r"""(?:api[_-]?key|apikey|secret|token|password|passwd|credentials?|auth)\s*[:=]\s*['"][^'"]{8,}['"]""", re.IGNORECASE),
    re.compile(r"""(?:sk|pk)[-_](?:live|test|prod)[-_]\w{10,}"""),
    re.compile(r"""(?:ghp|gho|ghu|ghs|ghr)_\w{30,}"""),
    re.compile(r"""(?:AKIA|ABIA|ACCA|ASIA)\w{12,}"""),
]

TODO_PATTERN = re.compile(r"\b(TODO|FIXME|HACK|XXX|WORKAROUND|TEMP|KLUDGE)\b", re.IGNORECASE)
CONSOLE_LOG_PATTERN = re.compile(r"\bconsole\.(log|debug|info|warn|error)\b")
COMMENTED_CODE_PATTERN = re.compile(r"^\s*//\s*(if|for|while|return|const|let|var|function|class|import|def |async )")


def run_cmd(cmd, timeout=30, cwd=None):
    """Run a command and return (exit_code, stdout, stderr)."""
    try:
        if isinstance(cmd, str):
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                               timeout=timeout, cwd=cwd)
        else:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=timeout, cwd=cwd)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -1, "", str(e)


def find_git_repos(scan_dirs, max_depth=4):
    """Auto-discover all git repos with remotes.

    Handles nested repos (e.g. ~/Desktop/Claude/ is a repo,
    but ~/Desktop/Claude/Finance/ is also its own repo).
    We keep descending to find child repos even when a parent has .git.
    """
    repos = []
    seen = set()

    for scan_dir in scan_dirs:
        d = Path(os.path.expanduser(scan_dir))
        if not d.exists():
            continue

        for root, dirs, _files in os.walk(d):
            depth = len(Path(root).relative_to(d).parts)
            if depth > max_depth:
                dirs.clear()
                continue

            dirs[:] = [x for x in dirs if x not in SKIP_DIRS]

            git_dir = Path(root) / ".git"
            if git_dir.exists() and git_dir.is_dir():
                repo_path = Path(root)
                real = str(repo_path.resolve())
                if real in seen:
                    continue
                seen.add(real)

                code, stdout, _ = run_cmd(
                    ["git", "-C", str(repo_path), "remote", "get-url", "origin"],
                    timeout=5
                )
                remote = stdout if code == 0 and stdout else None

                repo_name = repo_path.name
                if remote:
                    slug = remote.rstrip("/")
                    if slug.endswith(".git"):
                        slug = slug[:-4]
                    parts = slug.split("/")
                    if len(parts) >= 2:
                        repo_name = parts[-1]

                if repo_name in EXCLUDE_REPOS:
                    # Skip excluded repos but keep descending for child repos
                    has_child_repos = any(
                        (Path(root) / sub / ".git").exists() for sub in dirs
                    )
                    if not has_child_repos:
                        dirs.clear()
                    continue

                repos.append({
                    "name": repo_path.name,
                    "dir": str(repo_path),
                    "repo": repo_name,
                    "remote": remote,
                })

                # Check if any child directory also has its own .git
                # If so, keep descending. Otherwise, stop here.
                has_child_repos = any(
                    (Path(root) / sub / ".git").exists() for sub in dirs
                )
                if not has_child_repos:
                    dirs.clear()

    return sorted(repos, key=lambda r: r["name"].lower())


def iter_source_files(repo_dir):
    """Yield (Path, relative_path_str) for all non-binary source files."""
    d = Path(repo_dir)
    for f in d.rglob("*"):
        if any(part in SKIP_DIRS for part in f.parts):
            continue
        if f.is_file() and f.suffix.lower() not in BINARY_EXTS:
            try:
                rel = str(f.relative_to(d))
                yield f, rel
            except (OSError, ValueError):
                pass


def read_file_safe(path, max_bytes=512_000):
    """Read a file's text content, returning None on failure."""
    try:
        size = path.stat().st_size
        if size > max_bytes:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        return None


def match_repo(repos, name):
    """Find repos matching a name (case-insensitive substring)."""
    return [r for r in repos if name.lower() in r["name"].lower()]


# ---------------------------------------------------------------------------
# AUDIT mode
# ---------------------------------------------------------------------------

def audit_repo(repo):
    """Full health check on one repo."""
    d = Path(repo["dir"])
    result = {
        "name": repo["name"],
        "dir": repo["dir"],
        "remote": repo["remote"],
        "exists": d.exists(),
        "issues": [],
        "stats": {},
        "tests": {},
    }

    if not d.exists():
        result["issues"].append("Directory does not exist")
        return result

    # --- File stats ---
    all_files = []
    for f in d.rglob("*"):
        if any(part in SKIP_DIRS for part in f.parts):
            continue
        if f.is_file():
            try:
                all_files.append((f, f.stat().st_size, f.stat().st_mtime))
            except OSError:
                pass

    result["stats"] = {
        "file_count": len(all_files),
        "total_size_kb": sum(s for _, s, _ in all_files) // 1024,
        "last_modified": None,
    }

    if all_files:
        newest = max(all_files, key=lambda x: x[2])
        result["stats"]["last_modified"] = datetime.fromtimestamp(
            newest[2], tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M UTC")

    # --- Git status ---
    code, stdout, _ = run_cmd(["git", "status", "--porcelain"], cwd=repo["dir"])
    if code == 0 and stdout:
        result["stats"]["uncommitted"] = len(stdout.split("\n"))

    code, stdout, _ = run_cmd(["git", "log", "--oneline", "@{u}..HEAD"], cwd=repo["dir"])
    if code == 0 and stdout:
        result["stats"]["unpushed"] = len(stdout.split("\n"))

    # --- Tests ---
    result["tests"] = detect_tests(d)

    # --- Issues ---
    result["issues"] = find_issues(repo, d, all_files)

    return result


def detect_tests(d):
    """Detect test frameworks and whether tests exist."""
    info = {"has_tests": False, "framework": None}

    if (d / "package.json").exists():
        try:
            pkg = json.loads((d / "package.json").read_text(encoding="utf-8"))
            scripts = pkg.get("scripts", {})
            if "test" in scripts and "no test specified" not in scripts["test"]:
                info["has_tests"] = True
                info["framework"] = "npm test"
        except (json.JSONDecodeError, OSError):
            pass

    if any(d.rglob("test_*.py")) or any(d.rglob("*_test.py")) or (d / "tests").exists():
        info["has_tests"] = True
        info["framework"] = "pytest"

    if any(d.rglob("*.test.js")) or any(d.rglob("*.test.ts")) or \
       any(d.rglob("*.spec.js")) or any(d.rglob("*.spec.ts")):
        info["has_tests"] = True
        info["framework"] = info["framework"] or "jest/vitest"

    return info


def find_issues(repo, d, all_files):
    """Check for common issues."""
    issues = []

    if not (d / ".gitignore").exists():
        issues.append("No .gitignore file — risk of committing junk")

    # node_modules tracked
    if (d / "node_modules").exists():
        code, stdout, _ = run_cmd(["git", "ls-files", "node_modules/"], cwd=repo["dir"])
        if code == 0 and stdout:
            issues.append("node_modules/ is tracked in git")

    # Large files (>5MB) — only git-tracked files
    code, stdout, _ = run_cmd(["git", "ls-files"], cwd=repo["dir"])
    tracked_files = set(stdout.splitlines()) if code == 0 else set()
    for f, size, _ in all_files:
        if size > 5 * 1024 * 1024:
            rel = f.relative_to(d)
            # Normalize path separators for comparison with git ls-files
            rel_posix = str(rel).replace("\\", "/")
            if tracked_files and rel_posix not in tracked_files:
                continue
            mb = size / (1024 * 1024)
            issues.append(f"Large file: {rel} ({mb:.1f}MB)")

    # No README
    if not any((d / n).exists() for n in ["README.md", "readme.md", "README.txt", "README"]):
        issues.append("No README")

    # Stale
    if all_files:
        newest = max(f[2] for f in all_files)
        days = (datetime.now().timestamp() - newest) / 86400
        if days > 30:
            issues.append(f"Stale — no changes in {int(days)} days")

    # No remote
    if not repo["remote"]:
        issues.append("No git remote — not backed up")

    return issues


def format_audit_report(audits):
    """Format audit results as markdown."""
    lines = [
        "# pocketDEV — Audit Report",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Repos scanned:** {len(audits)}",
        "",
    ]

    total_issues = sum(len(a["issues"]) for a in audits)
    tested = sum(1 for a in audits if a["tests"]["has_tests"])
    passing = sum(1 for a in audits if a["tests"].get("passed"))
    failing = sum(1 for a in audits if a["tests"].get("passed") is False)
    no_tests = len(audits) - tested

    lines.append(f"**Quick summary:** {total_issues} issues found. "
                 f"Tests: {passing} passing, {failing} failing, {no_tests} with no tests.")
    lines.append("")

    for a in audits:
        if not a["exists"]:
            status = "MISSING"
        elif a["issues"]:
            status = f"{len(a['issues'])} ISSUE(S)"
        else:
            status = "HEALTHY"

        lines.append("---")
        lines.append(f"## {a['name']} — {status}")
        lines.append(f"**Location:** `{a['dir']}`")
        if a["remote"]:
            # Extract just the repo slug from URL
            url = a["remote"].rstrip("/")
            if url.endswith(".git"):
                url = url[:-4]
            slug = url.split("/")[-1]
            lines.append(f"**GitHub:** `{slug}`")
        lines.append("")

        if not a["exists"]:
            lines.append("Directory does not exist.")
            lines.append("")
            continue

        s = a["stats"]
        lines.append(f"**Files:** {s['file_count']} | "
                     f"**Size:** {s['total_size_kb']}KB | "
                     f"**Last changed:** {s['last_modified']}")

        if s.get("uncommitted"):
            lines.append(f"**Uncommitted:** {s['uncommitted']} file(s)")
        if s.get("unpushed"):
            lines.append(f"**Unpushed:** {s['unpushed']} commit(s)")

        lines.append("")

        t = a["tests"]
        if t["has_tests"]:
            label = "PASSING" if t.get("passed") else ("FAILING" if t.get("passed") is False else t["framework"])
            lines.append(f"**Tests:** {label}")
        else:
            lines.append("**Tests:** None configured")

        if a["issues"]:
            lines.append("\n**Issues found:**")
            for issue in a["issues"]:
                lines.append(f"- {issue}")
        else:
            lines.append("**Issues:** None detected")
        lines.append("")

    lines += [
        "---",
        "## For Claude (when processing this report)",
        "",
        "Read this report and for each tool with issues, propose fixes in plain language.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# REVIEW mode
# ---------------------------------------------------------------------------

def review_repo(repo):
    """Deep code quality review of a single repo."""
    d = Path(repo["dir"])
    review = {
        "name": repo["name"],
        "dir": repo["dir"],
        "remote": repo["remote"],
    }

    # --- File inventory ---
    file_stats = []
    for f, rel in iter_source_files(repo["dir"]):
        try:
            content = read_file_safe(f)
            loc = len(content.splitlines()) if content else 0
            file_stats.append({"path": rel, "lines": loc, "size": f.stat().st_size})
        except OSError:
            pass

    file_stats.sort(key=lambda x: x["lines"], reverse=True)
    review["file_count"] = len(file_stats)
    review["total_loc"] = sum(f["lines"] for f in file_stats)
    review["largest_files"] = file_stats[:10]

    # --- Code smells ---
    todos = []
    secret_hits = []
    console_logs = []
    commented_code = []
    long_functions = []

    for f, rel in iter_source_files(repo["dir"]):
        content = read_file_safe(f)
        if not content:
            continue

        lines = content.splitlines()

        for i, line in enumerate(lines, 1):
            m = TODO_PATTERN.search(line)
            if m:
                todos.append({"file": rel, "line": i, "tag": m.group(1).upper(),
                              "text": line.strip()[:120]})

            for pat in SECRET_PATTERNS:
                if pat.search(line):
                    secret_hits.append({"file": rel, "line": i,
                                        "text": line.strip()[:80] + "..."})
                    break

            if CONSOLE_LOG_PATTERN.search(line):
                console_logs.append({"file": rel, "line": i})

            if COMMENTED_CODE_PATTERN.match(line):
                commented_code.append({"file": rel, "line": i,
                                       "text": line.strip()[:100]})

        # Rough long-function detection (Python def/JS function blocks > 60 lines)
        func_start = None
        func_name = None
        indent_level = None
        for i, line in enumerate(lines, 1):
            fn_match = re.match(r'^(\s*)(def |async def |function |async function |const \w+ = (?:async )?\()', line)
            if fn_match:
                if func_start and indent_level is not None:
                    length = i - func_start
                    if length > 60:
                        long_functions.append({"file": rel, "line": func_start,
                                               "name": func_name, "lines": length})
                func_start = i
                func_name = line.strip()[:60]
                indent_level = len(fn_match.group(1))

        # Catch last function in file
        if func_start and indent_level is not None:
            length = len(lines) - func_start + 1
            if length > 60:
                long_functions.append({"file": rel, "line": func_start,
                                       "name": func_name, "lines": length})

    review["todos"] = todos
    review["secret_hits"] = secret_hits
    review["console_logs_count"] = len(console_logs)
    review["commented_code"] = commented_code[:20]
    review["long_functions"] = sorted(long_functions, key=lambda x: x["lines"], reverse=True)[:10]

    # --- Dependency health ---
    review["deps"] = check_dependencies(d)

    # --- Test coverage ---
    tests = detect_tests(d)
    test_files = []
    src_files = []
    for f, rel in iter_source_files(repo["dir"]):
        lower = rel.lower()
        if "test" in lower or "spec" in lower or rel.startswith("tests"):
            test_files.append(rel)
        elif f.suffix in {".py", ".js", ".ts", ".jsx", ".tsx"}:
            src_files.append(rel)

    review["tests"] = tests
    review["test_file_count"] = len(test_files)
    review["src_file_count"] = len(src_files)
    review["test_ratio"] = (f"{len(test_files)}/{len(src_files)}"
                           if src_files else "N/A")

    # --- Git activity ---
    code, stdout, _ = run_cmd(
        ["git", "log", "--oneline", "--since=30 days ago", "--no-merges"],
        cwd=repo["dir"]
    )
    review["recent_commits"] = len(stdout.splitlines()) if code == 0 and stdout else 0

    code, stdout, _ = run_cmd(
        ["git", "shortlog", "-sn", "--since=90 days ago"],
        cwd=repo["dir"]
    )
    review["contributors"] = stdout.strip() if code == 0 and stdout else "N/A"

    return review


def check_dependencies(d):
    """Check dependency health."""
    deps = {"manager": None, "count": 0, "outdated": [], "lockfile": False}

    if (d / "package.json").exists():
        deps["manager"] = "npm"
        try:
            pkg = json.loads((d / "package.json").read_text(encoding="utf-8"))
            all_deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            deps["count"] = len(all_deps)
        except (json.JSONDecodeError, OSError):
            pass
        deps["lockfile"] = (d / "package-lock.json").exists() or (d / "yarn.lock").exists()

        # Check outdated
        code, stdout, _ = run_cmd(["npm", "outdated", "--json"], cwd=str(d), timeout=60)
        if code != 0 and stdout:
            try:
                outdated = json.loads(stdout)
                for pkg_name, info in outdated.items():
                    current = info.get("current", "?")
                    latest = info.get("latest", "?")
                    if current != latest:
                        deps["outdated"].append(f"{pkg_name}: {current} → {latest}")
            except json.JSONDecodeError:
                pass

    elif (d / "requirements.txt").exists() or (d / "pyproject.toml").exists():
        deps["manager"] = "pip"
        req_file = d / "requirements.txt"
        if req_file.exists():
            try:
                reqs = [l.strip() for l in req_file.read_text(encoding="utf-8").splitlines()
                        if l.strip() and not l.startswith("#")]
                deps["count"] = len(reqs)
            except OSError:
                pass
        deps["lockfile"] = (d / "requirements.txt").exists()

    return deps


def format_review_report(review):
    """Format deep review as markdown."""
    lines = [
        "# pocketDEV — Code Review",
        f"**Tool:** {review['name']}",
        f"**Location:** `{review['dir']}`",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "---",
        "## Overview",
        "",
        f"- **Source files:** {review['file_count']}",
        f"- **Total lines of code:** {review['total_loc']:,}",
        f"- **Test files / source files:** {review['test_ratio']}",
        f"- **Commits (last 30 days):** {review['recent_commits']}",
        "",
    ]

    # Largest files
    if review["largest_files"]:
        lines += ["## Largest Files (by lines)", ""]
        lines.append("| File | Lines |")
        lines.append("|---|---|")
        for f in review["largest_files"]:
            lines.append(f"| `{f['path']}` | {f['lines']:,} |")
        lines.append("")

    # Long functions
    if review["long_functions"]:
        lines += ["## Long Functions (>60 lines)", "",
                  "These are candidates for breaking up.", ""]
        for fn in review["long_functions"]:
            lines.append(f"- `{fn['file']}:{fn['line']}` — {fn['name']} ({fn['lines']} lines)")
        lines.append("")

    # TODOs
    if review["todos"]:
        lines += [f"## TODOs & FIXMEs ({len(review['todos'])} found)", ""]
        tag_counts = Counter(t["tag"] for t in review["todos"])
        lines.append(f"Breakdown: {', '.join(f'{tag}: {n}' for tag, n in tag_counts.most_common())}")
        lines.append("")
        for t in review["todos"][:25]:
            lines.append(f"- `{t['file']}:{t['line']}` [{t['tag']}] {t['text']}")
        if len(review["todos"]) > 25:
            lines.append(f"- ... and {len(review['todos']) - 25} more")
        lines.append("")

    # Security
    if review["secret_hits"]:
        lines += [f"## Possible Secrets ({len(review['secret_hits'])} found)", "",
                  "**These need immediate review.**", ""]
        for s in review["secret_hits"][:10]:
            lines.append(f"- `{s['file']}:{s['line']}` — `{s['text']}`")
        lines.append("")

    # Console logs
    if review["console_logs_count"]:
        lines.append(f"## Console Logs: {review['console_logs_count']} found")
        lines.append("")

    # Commented-out code
    if review["commented_code"]:
        lines += [f"## Commented-Out Code ({len(review['commented_code'])} blocks)", ""]
        for c in review["commented_code"][:10]:
            lines.append(f"- `{c['file']}:{c['line']}` — `{c['text']}`")
        lines.append("")

    # Dependencies
    deps = review["deps"]
    if deps["manager"]:
        lines += ["## Dependencies", ""]
        lines.append(f"- **Manager:** {deps['manager']}")
        lines.append(f"- **Count:** {deps['count']}")
        lines.append(f"- **Lock file:** {'Yes' if deps['lockfile'] else 'No'}")
        if deps["outdated"]:
            lines.append(f"- **Outdated ({len(deps['outdated'])}):**")
            for o in deps["outdated"][:15]:
                lines.append(f"  - {o}")
        lines.append("")

    # Tests
    t = review["tests"]
    lines += ["## Tests", ""]
    if t["has_tests"]:
        lines.append(f"- **Framework:** {t['framework']}")
        lines.append(f"- **Test files:** {review['test_file_count']}")
    else:
        lines.append("- No tests configured")
    lines.append("")

    # Instructions for Claude
    lines += [
        "---",
        "## For Claude (when processing this review)",
        "",
        "You are acting as a senior developer reviewing this codebase.",
        "Prioritize findings by impact: security > correctness > maintainability > style.",
        "For each category with findings, propose concrete fixes with effort estimates.",
        "Group quick wins (under 10 minutes) separately from larger refactors.",
        "Do not fix anything without user approval.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# DIAGNOSE mode
# ---------------------------------------------------------------------------

def diagnose_repo(repo):
    """Gather diagnostic info for a broken/degraded tool."""
    d = Path(repo["dir"])
    diag = {
        "name": repo["name"],
        "dir": repo["dir"],
        "remote": repo["remote"],
    }

    # --- Recent changes ---
    code, stdout, _ = run_cmd(
        ["git", "log", "--oneline", "-20", "--no-merges"],
        cwd=repo["dir"]
    )
    diag["recent_commits"] = stdout if code == 0 else "Could not read git log"

    code, stdout, _ = run_cmd(
        ["git", "diff", "--stat", "HEAD~5..HEAD"],
        cwd=repo["dir"]
    )
    diag["recent_diff_stat"] = stdout if code == 0 else "N/A"

    # --- Uncommitted changes ---
    code, stdout, _ = run_cmd(["git", "status", "--short"], cwd=repo["dir"])
    diag["uncommitted"] = stdout if code == 0 and stdout else "Clean"

    code, stdout, _ = run_cmd(["git", "diff", "--stat"], cwd=repo["dir"])
    diag["uncommitted_diff"] = stdout if code == 0 and stdout else None

    # --- Run tests ---
    diag["test_output"] = None
    diag["test_passed"] = None
    tests = detect_tests(d)

    if tests["has_tests"]:
        if tests["framework"] == "pytest":
            code, stdout, stderr = run_cmd(
                ["python", "-m", "pytest", "-x", "--tb=short", "-q"],
                cwd=repo["dir"], timeout=120
            )
            diag["test_output"] = (stdout + "\n" + stderr).strip()
            diag["test_passed"] = code == 0

        elif tests["framework"] == "npm test":
            code, stdout, stderr = run_cmd(
                ["npm", "test", "--", "--watchAll=false"],
                cwd=repo["dir"], timeout=120
            )
            diag["test_output"] = (stdout + "\n" + stderr).strip()[-3000:]
            diag["test_passed"] = code == 0

    # --- Check for error logs ---
    log_files = []
    for pattern in ["*.log", "**/*.log", "**/error*", "**/*crash*"]:
        for f in d.glob(pattern):
            if f.is_file() and ".git" not in str(f):
                try:
                    size = f.stat().st_size
                    mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
                    # Only recent logs (last 7 days)
                    if (datetime.now(timezone.utc) - mtime).days <= 7:
                        tail = ""
                        if size > 0:
                            content = read_file_safe(f, max_bytes=50_000)
                            if content:
                                tail = "\n".join(content.splitlines()[-30:])
                        log_files.append({
                            "path": str(f.relative_to(d)),
                            "size": size,
                            "modified": mtime.strftime("%Y-%m-%d %H:%M UTC"),
                            "tail": tail,
                        })
                except OSError:
                    pass

    diag["logs"] = log_files

    # --- Dependency check ---
    diag["deps_ok"] = True
    if (d / "package.json").exists():
        if not (d / "node_modules").exists():
            diag["deps_ok"] = False
            diag["deps_issue"] = "node_modules/ missing — run npm install"
        else:
            code, stdout, _ = run_cmd(["npm", "ls", "--depth=0"], cwd=str(d), timeout=30)
            if code != 0:
                diag["deps_ok"] = False
                diag["deps_issue"] = "Dependency tree has errors"

    elif (d / "requirements.txt").exists():
        # Check if we're in a venv or can import key deps
        code, stdout, stderr = run_cmd(
            ["python", "-c", "import pkg_resources; pkg_resources.require(open('requirements.txt').readlines())"],
            cwd=str(d), timeout=15
        )
        if code != 0:
            diag["deps_ok"] = False
            diag["deps_issue"] = f"Missing Python dependencies: {stderr[:200]}"

    # --- Environment files ---
    env_file = d / ".env"
    env_example = d / ".env.example"
    if env_example.exists() and not env_file.exists():
        diag["env_issue"] = ".env.example exists but .env is missing"

    return diag


def format_diagnose_report(diag):
    """Format diagnostic report as markdown."""
    lines = [
        "# pocketDEV — Diagnostic Report",
        f"**Tool:** {diag['name']}",
        f"**Location:** `{diag['dir']}`",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "---",
        "## Recent Changes (last 20 commits)",
        "",
        "```",
        diag["recent_commits"],
        "```",
        "",
    ]

    if diag["recent_diff_stat"] and diag["recent_diff_stat"] != "N/A":
        lines += [
            "## What Changed Recently (last 5 commits)",
            "",
            "```",
            diag["recent_diff_stat"],
            "```",
            "",
        ]

    lines += ["## Working Tree", ""]
    if diag["uncommitted"] == "Clean":
        lines.append("No uncommitted changes.")
    else:
        lines += ["```", diag["uncommitted"], "```"]
        if diag.get("uncommitted_diff"):
            lines += ["", "```", diag["uncommitted_diff"], "```"]
    lines.append("")

    # Tests
    lines += ["## Tests", ""]
    if diag["test_output"]:
        status = "PASSED" if diag["test_passed"] else "FAILED"
        lines += [
            f"**Result:** {status}",
            "",
            "```",
            diag["test_output"][-3000:],
            "```",
            "",
        ]
    else:
        lines.append("No tests configured or could not run tests.")
        lines.append("")

    # Dependencies
    lines += ["## Dependencies", ""]
    if diag["deps_ok"]:
        lines.append("Dependencies look OK.")
    else:
        lines.append(f"**Problem:** {diag.get('deps_issue', 'Unknown issue')}")
    lines.append("")

    # Environment
    if diag.get("env_issue"):
        lines += ["## Environment", "", f"**Warning:** {diag['env_issue']}", ""]

    # Logs
    if diag["logs"]:
        lines += [f"## Recent Logs ({len(diag['logs'])} files)", ""]
        for log in diag["logs"]:
            lines.append(f"### `{log['path']}` ({log['modified']})")
            if log["tail"]:
                lines += ["```", log["tail"], "```"]
            lines.append("")

    # Instructions for Claude
    lines += [
        "---",
        "## For Claude (when processing this diagnostic)",
        "",
        "You are a senior developer diagnosing why this tool is broken or degraded.",
        "Start with the test output and recent changes — the bug is usually in the diff.",
        "Check if dependencies are the issue before blaming the code.",
        "Look for the simplest explanation first.",
        "Propose a fix with exact file and line references. Do not fix without approval.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="pocketdev",
        description="pocketDEV — Your senior developer on call."
    )
    parser.add_argument("--scan-dir", type=str, action="append",
                       help="Directory to scan for repos (repeatable)")

    subparsers = parser.add_subparsers(dest="mode", help="Operating mode")

    # audit
    p_audit = subparsers.add_parser("audit", help="Health scan across all repos")
    p_audit.add_argument("--tool", type=str, default=None,
                        help="Filter repos by name")
    p_audit.add_argument("--output", type=str, default=None,
                        help="Write report to file")

    # review
    p_review = subparsers.add_parser("review", help="Deep code review of one tool")
    p_review.add_argument("tool", type=str, help="Tool name to review")
    p_review.add_argument("--output", type=str, default=None,
                         help="Write report to file")

    # diagnose
    p_diagnose = subparsers.add_parser("diagnose", help="Diagnose a broken tool")
    p_diagnose.add_argument("tool", type=str, help="Tool name to diagnose")
    p_diagnose.add_argument("--output", type=str, default=None,
                           help="Write report to file")

    args = parser.parse_args()

    if not args.mode:
        parser.print_help()
        sys.exit(1)

    scan_dirs = args.scan_dir or [
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~/Documents"),
        os.path.expanduser("~/Projects"),
    ]

    print(f"[pocketDEV] Scanning: {', '.join(scan_dirs)}", file=sys.stderr)
    repos = find_git_repos(scan_dirs)

    if not repos:
        print("[pocketDEV] No git repos found.", file=sys.stderr)
        sys.exit(0)

    print(f"[pocketDEV] Found {len(repos)} repo(s).", file=sys.stderr)

    # --- AUDIT ---
    if args.mode == "audit":
        if args.tool:
            repos = match_repo(repos, args.tool)
        if not repos:
            print(f"[pocketDEV] No repos matching filter.", file=sys.stderr)
            sys.exit(0)

        audits = []
        for repo in repos:
            print(f"  Auditing {repo['name']}...", file=sys.stderr)
            audits.append(audit_repo(repo))

        report = format_audit_report(audits)

    # --- REVIEW ---
    elif args.mode == "review":
        matched = match_repo(repos, args.tool)
        if not matched:
            print(f"[pocketDEV] No repo matching '{args.tool}'.", file=sys.stderr)
            sys.exit(1)
        if len(matched) > 1:
            print(f"[pocketDEV] Multiple matches: {', '.join(r['name'] for r in matched)}",
                  file=sys.stderr)
            print(f"[pocketDEV] Be more specific.", file=sys.stderr)
            sys.exit(1)

        repo = matched[0]
        print(f"  Reviewing {repo['name']}...", file=sys.stderr)
        review = review_repo(repo)
        report = format_review_report(review)

    # --- DIAGNOSE ---
    elif args.mode == "diagnose":
        matched = match_repo(repos, args.tool)
        if not matched:
            print(f"[pocketDEV] No repo matching '{args.tool}'.", file=sys.stderr)
            sys.exit(1)
        if len(matched) > 1:
            print(f"[pocketDEV] Multiple matches: {', '.join(r['name'] for r in matched)}",
                  file=sys.stderr)
            print(f"[pocketDEV] Be more specific.", file=sys.stderr)
            sys.exit(1)

        repo = matched[0]
        print(f"  Diagnosing {repo['name']}...", file=sys.stderr)
        diag = diagnose_repo(repo)
        report = format_diagnose_report(diag)

    # --- Output ---
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"[pocketDEV] Report: {args.output}", file=sys.stderr)
    else:
        print(report)

    # Write pending flag for audit mode
    if args.mode == "audit":
        pending = Path(__file__).parent / "_audit-pending"
        pending.write_text(datetime.now().strftime('%Y-%m-%d %H:%M'), encoding="utf-8")


if __name__ == "__main__":
    main()
