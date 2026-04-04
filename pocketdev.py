"""
pocketDEV — Your senior developer on call.
Audits, reviews, and diagnoses your git-tracked projects.

Modes:
    audit                        Health scan across all discovered repos
    review <tool>                Deep code quality dive into one tool
    diagnose <tool>              Gather diagnostic info when something's broken
    snapshot                     Generate structured JSON snapshot of all repos
    backlog list [--status X]    List backlog entries, optionally filtered
    backlog stats                Show backlog counts by status and tool

Usage:
    python pocketdev.py audit                         # Scan all repos
    python pocketdev.py audit --tool "Finance"        # Filter by name
    python pocketdev.py review "Finance"              # Deep review one tool
    python pocketdev.py diagnose "Transcriptor"       # Diagnose a broken tool
    python pocketdev.py snapshot --output snap.json   # Parallel snapshot
    python pocketdev.py backlog list --status NEW     # Open backlog items
    python pocketdev.py backlog stats                 # Backlog summary
    python pocketdev.py --scan-dir ~/Projects audit   # Custom scan directory
"""

import json
import os
import re
import subprocess
import sys
import argparse
import time
import concurrent.futures
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

SKIP_DIRS = {".git", "node_modules", "__pycache__", "venv", ".venv", "dist",
             "build", ".next", ".nuxt", "coverage", ".tox", "egg-info",
             "_digests", "_conversations"}

# Repos to skip during discovery (parent/meta repos that aren't standalone tools)
EXCLUDE_REPOS = {"claude-backup"}

BINARY_EXTS = {".exe", ".dll", ".so", ".dylib", ".lib", ".pyd", ".pyc",
               ".whl", ".tar", ".gz", ".zip", ".7z", ".rar",
               ".mp4", ".m4a", ".mp3", ".wav", ".flac", ".avi", ".mkv",
               ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".ico", ".svg",
               ".pdf", ".doc", ".docx", ".xls", ".xlsx",
               ".ttf", ".otf", ".woff", ".woff2", ".eot"}

SECRET_PATTERNS = [
    # Generic key=value secrets
    (re.compile(r"""(?:api[_-]?key|apikey|secret[_-]?key|token|password|passwd|credentials?|auth[_-]?token|private[_-]?key)\s*[:=]\s*['"][^'"]{8,}['"]""", re.IGNORECASE), "Possible hardcoded secret"),
    # Stripe / service keys
    (re.compile(r"""(?:sk|pk|rk)[-_](?:live|test|prod)[-_]\w{10,}"""), "Stripe/service key"),
    # GitHub tokens
    (re.compile(r"""(?:ghp|gho|ghu|ghs|ghr)_\w{30,}"""), "GitHub token"),
    # AWS keys
    (re.compile(r"""(?:AKIA|ABIA|ACCA|ASIA)\w{12,}"""), "AWS access key"),
    # Private keys
    (re.compile(r"""-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"""), "Private key file"),
    # Connection strings
    (re.compile(r"""(?:mongodb|postgres|mysql|redis|amqp)://[^\s'"]{10,}""", re.IGNORECASE), "Database connection string"),
    # JWT tokens (three base64 segments separated by dots)
    (re.compile(r"""eyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}"""), "JWT token"),
    # Anthropic API keys
    (re.compile(r"""sk-ant-\w{20,}"""), "Anthropic API key"),
    # OpenAI API keys
    (re.compile(r"""sk-[A-Za-z0-9]{40,}"""), "OpenAI API key"),
    # Generic long hex/base64 secrets assigned to variables
    (re.compile(r"""(?:SECRET|KEY|TOKEN|PASS)\s*[:=]\s*['"][A-Za-z0-9+/=_-]{32,}['"]""", re.IGNORECASE), "Long secret value"),
]

# Sensitive file patterns that should never be committed
SENSITIVE_FILES = {
    ".env", ".env.local", ".env.production", ".env.staging", ".env.development",
    ".env.test", ".env.secret", ".npmrc", ".pypirc",
    "credentials.json", "service-account.json", "keyfile.json",
    "id_rsa", "id_ed25519", "id_ecdsa", "id_dsa",
    ".htpasswd", ".netrc", ".pgpass",
}

# Extensions that should never be tracked
SENSITIVE_EXTENSIONS = {".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"}

# Personal data patterns
PII_PATTERNS = [
    # Email addresses
    (re.compile(r"""[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"""), "Email address"),
    # Phone numbers — must have country code prefix (+40, +1, etc.) or explicit separator pattern
    # This avoids false positives on timestamps, IDs, and large numbers
    (re.compile(r"""\+\d{1,3}[-.\s]?\d{2,4}[-.\s]?\d{3,4}[-.\s]?\d{3,4}"""), "Phone number"),
    # Windows user paths (leak username)
    (re.compile(r"""[A-Z]:\\Users\\[^\\'"]+"""), "Windows user path (leaks username)"),
    # Unix home paths
    (re.compile(r"""/(?:home|Users)/[a-zA-Z0-9._-]+"""), "Home directory path (leaks username)"),
]

# Files where PII is expected/acceptable (don't flag these)
PII_IGNORE_FILES = {"package.json", "package-lock.json", "yarn.lock", "LICENSE",
                     "CONTRIBUTORS", "AUTHORS", ".mailmap", "pyproject.toml",
                     "setup.cfg", "setup.py"}

TODO_PATTERN = re.compile(r"\b(TODO|FIXME|HACK|XXX|WORKAROUND|TEMP|KLUDGE)\b", re.IGNORECASE)
CONSOLE_LOG_PATTERN = re.compile(r"\bconsole\.(log|debug|info|warn|error)\b")
COMMENTED_CODE_PATTERN = re.compile(r"^\s*//\s*(if|for|while|return|const|let|var|function|class|import|def |async )")


# Git subprocess result cache: {(repo_dir, command_tuple): (result, timestamp)}
_git_cache = {}
_GIT_CACHE_TTL = 60  # seconds


def run_cmd(cmd, timeout=30, cwd=None, cache_key=None):
    """Run a command and return (exit_code, stdout, stderr).

    If cache_key is provided, results are cached for _GIT_CACHE_TTL seconds.
    cache_key should be a hashable value, typically (cwd, tuple(cmd)).
    """
    if cache_key is not None and cache_key in _git_cache:
        result, ts = _git_cache[cache_key]
        if time.monotonic() - ts < _GIT_CACHE_TTL:
            return result

    try:
        if isinstance(cmd, str):
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                               timeout=timeout, cwd=cwd)
        else:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=timeout, cwd=cwd)
        result = (r.returncode, r.stdout.strip(), r.stderr.strip())
    except subprocess.TimeoutExpired:
        result = (-1, "", "TIMEOUT")
    except Exception as e:
        result = (-1, "", str(e))

    if cache_key is not None:
        _git_cache[cache_key] = (result, time.monotonic())

    return result


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
# RepositoryScanner — single-pass, lazily-cached scanning
# ---------------------------------------------------------------------------

class RepositoryScanner:
    """Lazily computes and caches scan results for a single repo.

    Each property runs at most once per instance. Modes pick what they need;
    shared work (tracked files, security scans) is never duplicated.
    """

    def __init__(self, repo):
        self.repo = repo
        self.d = Path(repo["dir"])
        self._tracked_files = None
        self._all_files = None
        self._tests_info = None
        self._test_result = None
        self._security = None
        self._dependencies = None

    # -- lazy properties --

    @property
    def tracked_files(self):
        if self._tracked_files is None:
            self._tracked_files = get_tracked_files(self.repo["dir"])
        return self._tracked_files

    @property
    def all_files(self):
        """List of (Path, size_bytes, mtime) for every non-skipped file."""
        if self._all_files is None:
            result = []
            for f in self.d.rglob("*"):
                if any(part in SKIP_DIRS for part in f.parts):
                    continue
                if f.is_file():
                    try:
                        st = f.stat()
                        result.append((f, st.st_size, st.st_mtime))
                    except OSError:
                        pass
            self._all_files = result
        return self._all_files

    @property
    def tests_info(self):
        if self._tests_info is None:
            self._tests_info = detect_tests(self.d)
        return self._tests_info

    @property
    def test_result(self):
        if self._test_result is None:
            self._test_result = run_tests(self.d, self.tests_info)
        return self._test_result

    @property
    def security(self):
        """Dict with secrets_found, pii_found, history_issues lists."""
        if self._security is None:
            rd = self.repo["dir"]
            self._security = {
                "secrets_found": scan_secrets(rd, self.d, self.tracked_files),
                "pii_found": scan_pii(rd, self.d, self.tracked_files),
                "history_issues": scan_history(rd),
            }
        return self._security

    @property
    def dependencies(self):
        if self._dependencies is None:
            self._dependencies = check_dependencies(self.d)
        return self._dependencies

    def scan_all(self):
        """Force-compute everything and return a summary dict."""
        return {
            "tracked_files": self.tracked_files,
            "all_files_count": len(self.all_files),
            "tests_info": self.tests_info,
            "test_result": self.test_result,
            "security": self.security,
            "dependencies": self.dependencies,
        }


# ---------------------------------------------------------------------------
# AUDIT mode
# ---------------------------------------------------------------------------

def audit_repo(repo):
    """Full health + security check on one repo."""
    d = Path(repo["dir"])
    result = {
        "name": repo["name"],
        "dir": repo["dir"],
        "remote": repo["remote"],
        "exists": d.exists(),
        "issues": {"critical": [], "warning": [], "info": []},
        "stats": {},
        "tests": {},
        "test_result": {},
    }

    if not d.exists():
        result["issues"]["critical"].append("Directory does not exist")
        return result

    scanner = RepositoryScanner(repo)
    all_files = scanner.all_files

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
    rd = repo["dir"]
    code, stdout, _ = run_cmd(["git", "status", "--porcelain"], cwd=rd,
                               cache_key=(rd, ("git", "status", "--porcelain")))
    if code == 0 and stdout:
        result["stats"]["uncommitted"] = len(stdout.split("\n"))

    code, stdout, _ = run_cmd(["git", "log", "--oneline", "@{u}..HEAD"], cwd=rd,
                               cache_key=(rd, ("git", "log", "--oneline", "@{u}..HEAD")))
    if code == 0 and stdout:
        result["stats"]["unpushed"] = len(stdout.split("\n"))

    # --- Tests ---
    result["tests"] = scanner.tests_info
    result["test_result"] = scanner.test_result

    # --- Issues (comprehensive) ---
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


def get_tracked_files(repo_dir):
    """Get set of git-tracked file paths (posix-style)."""
    code, stdout, _ = run_cmd(["git", "ls-files"], cwd=repo_dir,
                               cache_key=(repo_dir, ("git", "ls-files")))
    return set(stdout.splitlines()) if code == 0 else set()


def find_issues(repo, d, all_files):
    """Comprehensive health + security check."""
    issues = {"critical": [], "warning": [], "info": []}
    tracked = get_tracked_files(repo["dir"])

    # ---- CRITICAL: Security ----
    # Sensitive files tracked in git
    for tf in tracked:
        fname = Path(tf).name.lower()
        if fname in SENSITIVE_FILES:
            issues["critical"].append(f"SECRET FILE TRACKED: `{tf}` — remove from git immediately")
        if Path(tf).suffix.lower() in SENSITIVE_EXTENSIONS:
            issues["critical"].append(f"KEY FILE TRACKED: `{tf}` — private key in git")

    # Scan tracked source files for secrets
    secrets_found = scan_secrets(repo["dir"], d, tracked)
    for s in secrets_found[:15]:
        issues["critical"].append(f"SECRET IN CODE: `{s['file']}:{s['line']}` — {s['type']}")

    # Scan git history for previously committed sensitive files
    history_issues = scan_history(repo["dir"])
    for h in history_issues:
        issues["critical"].append(h)

    # PII in tracked files
    pii_found = scan_pii(repo["dir"], d, tracked)
    for p in pii_found[:10]:
        issues["critical"].append(f"PII LEAK: `{p['file']}:{p['line']}` — {p['type']}: {p['preview']}")

    # ---- WARNING: Hygiene ----
    if not (d / ".gitignore").exists():
        issues["warning"].append("No .gitignore file — risk of committing junk")

    # node_modules tracked
    if (d / "node_modules").exists():
        code, stdout, _ = run_cmd(["git", "ls-files", "node_modules/"], cwd=repo["dir"])
        if code == 0 and stdout:
            issues["warning"].append("node_modules/ is tracked in git")

    # .venv tracked
    if (d / ".venv").exists() or (d / "venv").exists():
        code, stdout, _ = run_cmd(["git", "ls-files", ".venv/ venv/"], cwd=repo["dir"])
        if code == 0 and stdout:
            issues["warning"].append("Virtual environment tracked in git")

    # Large tracked files (>5MB)
    for f, size, _ in all_files:
        if size > 5 * 1024 * 1024:
            rel = f.relative_to(d)
            rel_posix = str(rel).replace("\\", "/")
            if tracked and rel_posix not in tracked:
                continue
            mb = size / (1024 * 1024)
            issues["warning"].append(f"Large file: {rel} ({mb:.1f}MB)")

    # Missing lockfile
    if (d / "package.json").exists():
        if not (d / "package-lock.json").exists() and not (d / "yarn.lock").exists():
            issues["warning"].append("No lockfile (package-lock.json or yarn.lock)")

    py_files = [tf for tf in tracked if tf.endswith(".py")]
    if py_files and not (d / "requirements.txt").exists() and not (d / "pyproject.toml").exists():
        issues["warning"].append("Python files but no requirements.txt or pyproject.toml")

    # No README
    if not any((d / n).exists() for n in ["README.md", "readme.md", "README.txt", "README"]):
        issues["warning"].append("No README")

    # No LICENSE (matters for public repos)
    if not any((d / n).exists() for n in ["LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE"]):
        issues["info"].append("No LICENSE file")

    # ---- INFO: Operational ----
    # Stale
    if all_files:
        newest = max(f[2] for f in all_files)
        days = (datetime.now().timestamp() - newest) / 86400
        if days > 30:
            issues["info"].append(f"Stale — no changes in {int(days)} days")

    # No remote
    if not repo["remote"]:
        issues["warning"].append("No git remote — not backed up")

    # Diverged from remote
    if repo["remote"]:
        code, stdout, _ = run_cmd(["git", "rev-list", "--count", "HEAD..@{u}"], cwd=repo["dir"])
        if code == 0 and stdout.strip() and int(stdout.strip()) > 0:
            issues["info"].append(f"Behind remote by {stdout.strip()} commit(s) — pull needed")

    return issues


def scan_secrets(repo_dir, d, tracked):
    """Scan all tracked source files for hardcoded secrets."""
    hits = []
    for tf in tracked:
        fpath = d / tf.replace("/", os.sep)
        if not fpath.is_file():
            continue
        if fpath.suffix.lower() in BINARY_EXTS:
            continue
        # Skip very large files
        try:
            if fpath.stat().st_size > 512_000:
                continue
        except OSError:
            continue

        content = read_file_safe(fpath)
        if not content:
            continue

        for i, line in enumerate(content.splitlines(), 1):
            # Skip comments that just mention the word "password" etc.
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                # Only flag comments if they contain actual key-looking values
                if not re.search(r"""['"][A-Za-z0-9+/=_-]{20,}['"]""", line):
                    continue

            for pattern, secret_type in SECRET_PATTERNS:
                if pattern.search(line):
                    hits.append({
                        "file": tf,
                        "line": i,
                        "type": secret_type,
                        "text": stripped[:80],
                    })
                    break  # one hit per line

    return hits


def scan_pii(repo_dir, d, tracked):
    """Scan tracked files for personal data that shouldn't be public."""
    hits = []
    data_exts = {".csv", ".json", ".jsonl", ".tsv", ".txt", ".md", ".log",
                 ".py", ".js", ".ts", ".sh", ".html", ".yml", ".yaml"}

    for tf in tracked:
        fname = Path(tf).name.lower()
        if fname in PII_IGNORE_FILES:
            continue
        fpath = d / tf.replace("/", os.sep)
        if not fpath.is_file():
            continue
        if fpath.suffix.lower() not in data_exts:
            continue
        try:
            if fpath.stat().st_size > 512_000:
                continue
        except OSError:
            continue

        content = read_file_safe(fpath)
        if not content:
            continue

        for i, line in enumerate(content.splitlines(), 1):
            for pattern, pii_type in PII_PATTERNS:
                m = pattern.search(line)
                if m:
                    match_text = m.group(0)
                    # Skip obvious false positives
                    if pii_type == "Email address":
                        # Skip example/placeholder/test emails
                        email_lower = match_text.lower()
                        if any(x in email_lower for x in [
                            "example.com", "test.com", "placeholder", "noreply",
                            "github.com", "users.noreply", "@email.com", "@e.com",
                            "@test.", "@fake.", "@dummy.", "@localhost",
                            "@example.", "no-reply", "donotreply",
                        ]):
                            continue
                        # Skip very short local parts (likely test data)
                        local_part = email_lower.split("@")[0]
                        if len(local_part) <= 2:
                            continue
                    if pii_type == "Phone number":
                        # Must start with + to count
                        if not match_text.startswith("+"):
                            continue
                    if pii_type in ("Windows user path (leaks username)", "Home directory path (leaks username)"):
                        # Only flag if it's an actual literal path, not a variable/template
                        if any(x in line for x in ["$HOME", "${", "os.homedir", "expanduser",
                                "Path.home", "__file__", "process.env"]):
                            continue

                    hits.append({
                        "file": tf,
                        "line": i,
                        "type": pii_type,
                        "preview": match_text[:60],
                    })
                    break  # one hit per line

    return hits


def scan_history(repo_dir):
    """Scan git history for previously committed sensitive content."""
    issues = []

    # Check if sensitive files were ever committed (even if now deleted/gitignored)
    for fname in SENSITIVE_FILES:
        code, stdout, _ = run_cmd(
            ["git", "log", "--all", "--diff-filter=A", "--name-only", "--format=", "--", f"**/{fname}", fname],
            cwd=repo_dir, timeout=10
        )
        if code == 0 and stdout.strip():
            files = [f for f in stdout.strip().splitlines() if f.strip()]
            if files:
                issues.append(f"HISTORY: `{fname}` was committed in the past — secrets may be in git history")

    # Check for key files ever committed
    for ext in SENSITIVE_EXTENSIONS:
        code, stdout, _ = run_cmd(
            ["git", "log", "--all", "--diff-filter=A", "--name-only", "--format=", "--", f"*{ext}"],
            cwd=repo_dir, timeout=10
        )
        if code == 0 and stdout.strip():
            files = [f for f in stdout.strip().splitlines() if f.strip()]
            for f in files[:3]:
                issues.append(f"HISTORY: Key file `{f}` was committed — may need history rewrite")

    # Check for large binary files in history (>10MB that are no longer tracked)
    code, stdout, _ = run_cmd(
        ["git", "rev-list", "--objects", "--all"],
        cwd=repo_dir, timeout=15
    )
    if code == 0 and stdout:
        # This is lightweight — just check if there are blob objects for known data extensions
        code2, stdout2, _ = run_cmd(
            ["git", "log", "--all", "--diff-filter=D", "--name-only", "--format=",
             "--", "*.mp4", "*.m4a", "*.mp3", "*.csv", "*.jsonl", "*.sqlite", "*.db"],
            cwd=repo_dir, timeout=10
        )
        if code2 == 0 and stdout2.strip():
            deleted_data = [f for f in stdout2.strip().splitlines() if f.strip()]
            if deleted_data:
                count = len(set(deleted_data))
                issues.append(f"HISTORY: {count} data file(s) deleted but still in git history — repo bloat")

    return issues


def run_tests(d, tests_info):
    """Actually execute the test suite and return result."""
    if not tests_info["has_tests"]:
        return {"ran": False, "passed": None, "output": None}

    if tests_info["framework"] == "pytest":
        code, stdout, stderr = run_cmd(
            ["python", "-m", "pytest", "-x", "--tb=short", "-q"],
            cwd=str(d), timeout=120
        )
        output = (stdout + "\n" + stderr).strip()
        return {"ran": True, "passed": code == 0, "output": output[-500:]}

    elif tests_info["framework"] == "npm test":
        code, stdout, stderr = run_cmd(
            ["npm", "test", "--", "--watchAll=false"],
            cwd=str(d), timeout=120
        )
        output = (stdout + "\n" + stderr).strip()
        return {"ran": True, "passed": code == 0, "output": output[-500:]}

    return {"ran": False, "passed": None, "output": None}


def count_issues(issues_dict):
    """Count total issues across all severity levels."""
    return sum(len(v) for v in issues_dict.values())


def format_audit_report(audits):
    """Format audit results as markdown with severity levels."""
    lines = [
        "# pocketDEV — Audit Report",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Repos scanned:** {len(audits)}",
        "",
    ]

    total_critical = sum(len(a["issues"]["critical"]) for a in audits)
    total_warnings = sum(len(a["issues"]["warning"]) for a in audits)
    total_info = sum(len(a["issues"]["info"]) for a in audits)
    tested = sum(1 for a in audits if a["tests"]["has_tests"])
    test_ran = sum(1 for a in audits if a["test_result"].get("ran"))
    passing = sum(1 for a in audits if a["test_result"].get("passed") is True)
    failing = sum(1 for a in audits if a["test_result"].get("passed") is False)
    no_tests = len(audits) - tested

    summary_parts = []
    if total_critical:
        summary_parts.append(f"**{total_critical} CRITICAL**")
    if total_warnings:
        summary_parts.append(f"{total_warnings} warnings")
    if total_info:
        summary_parts.append(f"{total_info} info")
    if not summary_parts:
        summary_parts.append("All clean")

    lines.append(f"**Issues:** {', '.join(summary_parts)}")
    lines.append(f"**Tests:** {passing} passing, {failing} failing, {no_tests} with no tests"
                 + (f" ({test_ran} suites executed)" if test_ran else ""))
    lines.append("")

    # Sort: repos with critical issues first, then warnings, then clean
    def sort_key(a):
        c = len(a["issues"]["critical"])
        w = len(a["issues"]["warning"])
        return (-c, -w)

    for a in sorted(audits, key=sort_key):
        issues = a["issues"]
        total = count_issues(issues)

        if not a["exists"]:
            status = "MISSING"
        elif issues["critical"]:
            status = f"CRITICAL — {len(issues['critical'])} security issue(s)"
        elif issues["warning"]:
            status = f"{len(issues['warning'])} WARNING(S)"
        elif issues["info"]:
            status = f"OK — {len(issues['info'])} note(s)"
        else:
            status = "HEALTHY"

        lines.append("---")
        lines.append(f"## {a['name']} — {status}")
        lines.append(f"**Location:** `{a['dir']}`")
        if a["remote"]:
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

        # Tests
        t = a["tests"]
        tr = a["test_result"]
        if tr.get("ran"):
            if tr["passed"]:
                lines.append(f"**Tests:** PASSING ({t['framework']})")
            else:
                lines.append(f"**Tests:** FAILING ({t['framework']})")
                if tr.get("output"):
                    lines.append(f"\n```\n{tr['output']}\n```")
        elif t["has_tests"]:
            lines.append(f"**Tests:** Detected ({t['framework']}) — not executed")
        else:
            lines.append("**Tests:** None configured")

        # Issues by severity
        if issues["critical"]:
            lines.append("\n**CRITICAL (fix before pushing to GitHub):**")
            for issue in issues["critical"]:
                lines.append(f"- {issue}")

        if issues["warning"]:
            lines.append("\n**Warnings:**")
            for issue in issues["warning"]:
                lines.append(f"- {issue}")

        if issues["info"]:
            lines.append("\n**Info:**")
            for issue in issues["info"]:
                lines.append(f"- {issue}")

        if total == 0:
            lines.append("**Issues:** None detected")
        lines.append("")

    lines += [
        "---",
        "## For Claude (when processing this report)",
        "",
        "Read this report. CRITICAL issues must be fixed before any push to GitHub.",
        "For each critical issue, provide the exact fix command.",
        "For history contamination, provide the `git filter-repo` command to erase it.",
        "Security > correctness > maintainability > style.",
        "Do not fix anything without user approval.",
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

    # --- Dependency health (via scanner) ---
    scanner = RepositoryScanner(repo)
    review["deps"] = scanner.dependencies

    # --- Test coverage ---
    tests = scanner.tests_info
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

    # --- Run tests (via scanner) ---
    scanner = RepositoryScanner(repo)
    diag["test_output"] = None
    diag["test_passed"] = None

    if scanner.tests_info["has_tests"]:
        tr = scanner.test_result
        if tr.get("ran"):
            diag["test_output"] = tr.get("output")
            diag["test_passed"] = tr.get("passed")

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
# SNAPSHOT mode
# ---------------------------------------------------------------------------

def _snapshot_git_info(repo):
    """Collect git branch, commit history, and sync status for a snapshot."""
    rd = repo["dir"]
    git_info = {}

    code, stdout, _ = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=rd,
                               cache_key=(rd, ("git", "rev-parse", "--abbrev-ref", "HEAD")))
    git_info["branch"] = stdout if code == 0 else None

    code, stdout, _ = run_cmd(
        ["git", "log", "--oneline", "--since=30 days ago", "--no-merges"],
        cwd=rd, cache_key=(rd, ("git", "log", "--oneline", "--since=30 days ago", "--no-merges"))
    )
    git_info["commits_30d"] = len(stdout.splitlines()) if code == 0 and stdout else 0

    code, stdout, _ = run_cmd(
        ["git", "log", "-1", "--format=%aI"],
        cwd=rd, cache_key=(rd, ("git", "log", "-1", "--format=%aI"))
    )
    git_info["last_commit_date"] = stdout if code == 0 and stdout else None

    code, stdout, _ = run_cmd(
        ["git", "log", "-1", "--format=%s"],
        cwd=rd, cache_key=(rd, ("git", "log", "-1", "--format=%s"))
    )
    git_info["last_commit_msg"] = stdout if code == 0 and stdout else None

    code, stdout, _ = run_cmd(["git", "status", "--porcelain"], cwd=rd,
                               cache_key=(rd, ("git", "status", "--porcelain")))
    git_info["uncommitted"] = len(stdout.splitlines()) if code == 0 and stdout else 0

    code, stdout, _ = run_cmd(["git", "log", "--oneline", "@{u}..HEAD"], cwd=rd,
                               cache_key=(rd, ("git", "log", "--oneline", "@{u}..HEAD")))
    git_info["unpushed"] = len(stdout.splitlines()) if code == 0 and stdout else 0

    code, stdout, _ = run_cmd(["git", "rev-list", "--count", "HEAD..@{u}"], cwd=rd,
                               cache_key=(rd, ("git", "rev-list", "--count", "HEAD..@{u}")))
    git_info["behind_remote"] = int(stdout.strip()) if code == 0 and stdout.strip().isdigit() else 0

    return git_info


def _snapshot_files(repo_dir, tracked):
    """Compute extension counts, LOC, and largest files for a snapshot."""
    d = Path(repo_dir)
    ext_counter = Counter()
    file_lines = []
    total_loc = 0

    for tf in tracked:
        fpath = d / tf.replace("/", os.sep)
        if not fpath.is_file():
            continue
        ext = fpath.suffix.lower() if fpath.suffix else "(none)"
        ext_counter[ext] += 1
        if fpath.suffix.lower() not in BINARY_EXTS:
            content = read_file_safe(fpath)
            if content:
                loc = len(content.splitlines())
                total_loc += loc
                file_lines.append({"path": tf, "lines": loc})

    file_lines.sort(key=lambda x: x["lines"], reverse=True)

    return {
        "total": len(tracked),
        "by_extension": dict(ext_counter.most_common()),
        "largest": file_lines[:10],
        "total_loc": total_loc,
    }


def _snapshot_structure(repo_dir, tracked, has_tests):
    """Check README, LICENSE, gitignore, and find entrypoints for a snapshot."""
    d = Path(repo_dir)

    has_readme = any((d / n).exists() for n in ["README.md", "readme.md", "README.txt", "README"])
    has_license = any((d / n).exists() for n in ["LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE"])
    has_gitignore = (d / ".gitignore").exists()
    has_tests_dir = (d / "tests").exists() or (d / "test").exists()

    entrypoints = []
    for tf in tracked:
        fpath = d / tf.replace("/", os.sep)
        if fpath.suffix.lower() == ".sh":
            entrypoints.append(tf)
            continue
        if fpath.suffix.lower() in BINARY_EXTS:
            continue
        content = read_file_safe(fpath)
        if content and ('if __name__' in content or 'def main(' in content):
            entrypoints.append(tf)

    if (d / "package.json").exists():
        try:
            pkg = json.loads((d / "package.json").read_text(encoding="utf-8"))
            scripts = pkg.get("scripts", {})
            if scripts:
                entrypoints.append(f"npm scripts: {', '.join(scripts.keys())}")
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "has_readme": has_readme,
        "has_license": has_license,
        "has_gitignore": has_gitignore,
        "has_tests": has_tests_dir or has_tests,
        "entrypoints": entrypoints,
    }


def snapshot_repo(repo):
    """Generate a structured dict of repo health data for agent consumption."""
    d = Path(repo["dir"])
    snap = {
        "name": repo["name"],
        "dir": repo["dir"],
        "remote": repo["remote"],
        "exists": d.exists(),
    }

    if not d.exists():
        return snap

    scanner = RepositoryScanner(repo)

    # Git info
    snap["git"] = _snapshot_git_info(repo)

    # File stats
    snap["files"] = _snapshot_files(repo["dir"], scanner.tracked_files)

    # Tests
    tr = scanner.test_result
    snap["tests"] = {
        "framework": scanner.tests_info["framework"],
        "has_tests": scanner.tests_info["has_tests"],
        "ran": tr.get("ran", False),
        "passed": tr.get("passed"),
        "output_tail": (tr.get("output") or "")[-300:] or None,
    }

    # Security
    sec = scanner.security
    sensitive_tracked = []
    for tf in scanner.tracked_files:
        fname = Path(tf).name.lower()
        if fname in SENSITIVE_FILES or Path(tf).suffix.lower() in SENSITIVE_EXTENSIONS:
            sensitive_tracked.append(tf)

    details = []
    for s in sec["secrets_found"][:3]:
        details.append(f"SECRET {s['file']}:{s['line']} — {s['type']}")
    for p in sec["pii_found"][:2]:
        details.append(f"PII {p['file']}:{p['line']} — {p['type']}")

    snap["security"] = {
        "secrets_found": len(sec["secrets_found"]),
        "pii_found": len(sec["pii_found"]),
        "sensitive_files_tracked": sensitive_tracked,
        "history_issues": len(sec["history_issues"]),
        "details": details[:5],
    }

    # Dependencies
    deps = scanner.dependencies
    snap["dependencies"] = {
        "manager": deps["manager"],
        "count": deps["count"],
        "lockfile": deps["lockfile"],
        "outdated": len(deps["outdated"]),
    }

    # Structure
    snap["structure"] = _snapshot_structure(
        repo["dir"], scanner.tracked_files, scanner.tests_info["has_tests"]
    )

    return snap


def _snapshot_one(repo):
    """Snapshot a single repo and print progress. Used by ThreadPoolExecutor."""
    print(f"  Snapshotting {repo['name']}...", file=sys.stderr)
    return snapshot_repo(repo)


def snapshot_all(repos):
    """Generate a full snapshot across all repos (parallelized)."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        snapshots = list(pool.map(_snapshot_one, repos))

    total_loc = sum(s.get("files", {}).get("total_loc", 0) for s in snapshots)
    repos_with_tests = sum(1 for s in snapshots if s.get("tests", {}).get("has_tests"))
    repos_with_critical = sum(
        1 for s in snapshots
        if (s.get("security", {}).get("secrets_found", 0) > 0
            or s.get("security", {}).get("sensitive_files_tracked")
            or s.get("security", {}).get("history_issues", 0) > 0)
    )

    today = datetime.now().strftime("%Y-%m-%d")
    repos_changed_today = sum(
        1 for s in snapshots
        if s.get("git", {}).get("last_commit_date", "") and
           s["git"]["last_commit_date"].startswith(today)
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_repos": len(snapshots),
            "total_loc": total_loc,
            "repos_with_tests": repos_with_tests,
            "repos_with_critical_issues": repos_with_critical,
            "repos_changed_today": repos_changed_today,
        },
        "repos": snapshots,
    }


# ---------------------------------------------------------------------------
# Backlog
# ---------------------------------------------------------------------------

_BACKLOG_ENTRY_RE = re.compile(
    r"^###\s+\[(?P<status>[A-Z]+)\]\s+(?P<title>.+)$"
)
_BACKLOG_TOOL_RE = re.compile(r"^##\s+(?P<tool>.+)$")


def parse_backlog(backlog_path=None):
    """Parse _backlog.md into a list of entry dicts."""
    if backlog_path is None:
        backlog_path = Path(__file__).parent / "_backlog.md"
    else:
        backlog_path = Path(backlog_path)

    if not backlog_path.exists():
        return []

    text = backlog_path.read_text(encoding="utf-8")
    entries = []
    current_tool = None

    for line in text.splitlines():
        tool_m = _BACKLOG_TOOL_RE.match(line)
        if tool_m:
            current_tool = tool_m.group("tool").strip()
            continue

        entry_m = _BACKLOG_ENTRY_RE.match(line)
        if entry_m:
            entries.append({
                "tool": current_tool or "Unknown",
                "status": entry_m.group("status"),
                "title": entry_m.group("title").strip(),
            })

    return entries


def backlog_list(entries, status_filter=None):
    """Print backlog entries grouped by tool, optionally filtered by status."""
    if status_filter:
        entries = [e for e in entries if e["status"].upper() == status_filter.upper()]

    if not entries:
        print("No backlog entries found.")
        return

    by_tool = {}
    for e in entries:
        by_tool.setdefault(e["tool"], []).append(e)

    for tool, items in by_tool.items():
        print(f"\n{tool}")
        print("-" * len(tool))
        for item in items:
            print(f"  [{item['status']}] {item['title']}")

    print(f"\nTotal: {len(entries)} entries")


def backlog_stats(entries):
    """Print backlog statistics by status and tool."""
    if not entries:
        print("No backlog entries found.")
        return

    status_counts = Counter(e["status"] for e in entries)
    tool_counts = Counter(e["tool"] for e in entries)

    print("\nBy status:")
    for status, count in status_counts.most_common():
        print(f"  [{status}] {count}")

    print(f"\nBy tool:")
    for tool, count in tool_counts.most_common():
        print(f"  {tool}: {count}")

    print(f"\nTotal: {len(entries)} entries")


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

    # snapshot
    p_snapshot = subparsers.add_parser("snapshot", help="Generate structured JSON for Claude agent")
    p_snapshot.add_argument("--output", type=str, default=None,
                           help="Write snapshot to file (default: stdout)")

    # backlog
    p_backlog = subparsers.add_parser("backlog", help="Manage the improvement backlog")
    backlog_sub = p_backlog.add_subparsers(dest="backlog_action", help="Backlog action")
    p_bl_list = backlog_sub.add_parser("list", help="List backlog entries")
    p_bl_list.add_argument("--status", type=str, default=None,
                           help="Filter by status (e.g. NEW, DONE, APPROVED)")
    backlog_sub.add_parser("stats", help="Show backlog statistics")

    args = parser.parse_args()

    if not args.mode:
        parser.print_help()
        sys.exit(1)

    # Handle backlog before repo scanning (doesn't need repos)
    if args.mode == "backlog":
        entries = parse_backlog()
        if not hasattr(args, 'backlog_action') or not args.backlog_action:
            p_backlog.print_help()
            sys.exit(1)
        if args.backlog_action == "list":
            backlog_list(entries, status_filter=args.status)
        elif args.backlog_action == "stats":
            backlog_stats(entries)
        sys.exit(0)

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

    # --- SNAPSHOT ---
    elif args.mode == "snapshot":
        snapshot = snapshot_all(repos)
        report = json.dumps(snapshot, indent=2, default=str)

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
