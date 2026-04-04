"""
Tests for pocketDEV core scanning functions.

Covers: scan_secrets, scan_pii, find_issues, parse_backlog,
        match_repo, get_tracked_files.
"""

import importlib
import os
import textwrap
from pathlib import Path

import pytest

# Import the module (filename has no extension convention issues)
pocketdev = importlib.import_module("pocketdev")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: Path, content: str):
    """Write content to a file, creating parents as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_repo(tmp_path, files=None, tracked=None):
    """Create a minimal fake repo structure.

    files: dict of {relative_path: content}
    tracked: list of tracked file paths (posix). If None, all files are tracked.
    """
    (tmp_path / ".git").mkdir()
    files = files or {}
    for rel, content in files.items():
        _write(tmp_path / rel, content)
    if tracked is None:
        tracked = list(files.keys())
    return tracked


# ---------------------------------------------------------------------------
# scan_secrets
# ---------------------------------------------------------------------------

class TestScanSecrets:
    """Tests for secret detection in source files."""

    def test_detects_api_key(self, tmp_path):
        tracked = _make_repo(tmp_path, {
            "config.py": 'API_KEY = "sk_live_abc123xyz456def789"',
        })
        hits = pocketdev.scan_secrets(str(tmp_path), tmp_path, set(tracked))
        assert len(hits) >= 1
        assert any("secret" in h["type"].lower() or "key" in h["type"].lower()
                    or "Stripe" in h["type"] for h in hits)

    def test_detects_github_token(self, tmp_path):
        # Use a variable name that won't trigger the generic secret pattern first
        tracked = _make_repo(tmp_path, {
            "deploy.sh": 'GH="ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789"',
        })
        hits = pocketdev.scan_secrets(str(tmp_path), tmp_path, set(tracked))
        assert len(hits) >= 1
        assert any("GitHub" in h["type"] for h in hits)

    def test_detects_aws_key(self, tmp_path):
        tracked = _make_repo(tmp_path, {
            "aws.py": 'access_key = "AKIAIOSFODNN7EXAMPLE"',
        })
        hits = pocketdev.scan_secrets(str(tmp_path), tmp_path, set(tracked))
        assert len(hits) >= 1
        assert any("AWS" in h["type"] for h in hits)

    def test_detects_connection_string(self, tmp_path):
        tracked = _make_repo(tmp_path, {
            "db.py": 'DB_URL = "postgres://admin:hunter2@db.example.com:5432/mydb"',
        })
        hits = pocketdev.scan_secrets(str(tmp_path), tmp_path, set(tracked))
        assert len(hits) >= 1
        assert any("connection" in h["type"].lower() or "Database" in h["type"]
                    for h in hits)

    def test_detects_jwt_token(self, tmp_path):
        # A realistic-looking JWT (three base64url segments)
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiYWRtaW4iOnRydWV9.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        # Use a variable name that won't trigger the generic pattern first
        tracked = _make_repo(tmp_path, {
            "auth.py": f'data = "{jwt}"',
        })
        hits = pocketdev.scan_secrets(str(tmp_path), tmp_path, set(tracked))
        assert len(hits) >= 1
        assert any("JWT" in h["type"] for h in hits)

    def test_detects_anthropic_key(self, tmp_path):
        # sk-ant- pattern requires 20+ word chars after prefix.
        # Use a key without hyphens after sk-ant- so \w{20,} matches.
        tracked = _make_repo(tmp_path, {
            "llm.py": 'data = "sk-ant-abcdefghijklmnopqrstuvwxyz"',
        })
        hits = pocketdev.scan_secrets(str(tmp_path), tmp_path, set(tracked))
        assert len(hits) >= 1
        assert any("Anthropic" in h["type"] for h in hits)

    def test_comment_without_value_not_flagged(self, tmp_path):
        tracked = _make_repo(tmp_path, {
            "app.py": textwrap.dedent("""\
                # Set the password in your .env file
                // TODO: add password validation
                # The api_key comes from environment variables
            """),
        })
        hits = pocketdev.scan_secrets(str(tmp_path), tmp_path, set(tracked))
        assert len(hits) == 0, f"Comments mentioning 'password' should not be flagged: {hits}"

    def test_comment_with_actual_secret_flagged(self, tmp_path):
        tracked = _make_repo(tmp_path, {
            "app.py": '# password = "aBcDeFgHiJkLmNoPqRsTuVwXyZ012345"',
        })
        hits = pocketdev.scan_secrets(str(tmp_path), tmp_path, set(tracked))
        # Comment contains a long secret-looking value, should be flagged
        assert len(hits) >= 1

    def test_skips_binary_files(self, tmp_path):
        tracked = _make_repo(tmp_path, {
            "image.png": "not really a png but has api_key = 'secret12345678'",
        })
        hits = pocketdev.scan_secrets(str(tmp_path), tmp_path, set(tracked))
        assert len(hits) == 0

    def test_skips_untracked_files(self, tmp_path):
        _make_repo(tmp_path, {
            "secret.py": 'API_KEY = "sk_live_abc123xyz456def789"',
        }, tracked=[])  # nothing tracked
        hits = pocketdev.scan_secrets(str(tmp_path), tmp_path, set())
        assert len(hits) == 0


# ---------------------------------------------------------------------------
# scan_pii
# ---------------------------------------------------------------------------

class TestScanPii:
    """Tests for PII detection with false-positive filtering."""

    def test_detects_real_email(self, tmp_path):
        tracked = _make_repo(tmp_path, {
            "config.py": 'admin_email = "john.smith@company.org"',
        })
        hits = pocketdev.scan_pii(str(tmp_path), tmp_path, set(tracked))
        assert len(hits) >= 1
        assert any("Email" in h["type"] for h in hits)

    def test_skips_example_email(self, tmp_path):
        tracked = _make_repo(tmp_path, {
            "config.py": 'email = "user@example.com"',
        })
        hits = pocketdev.scan_pii(str(tmp_path), tmp_path, set(tracked))
        emails = [h for h in hits if "Email" in h["type"]]
        assert len(emails) == 0

    def test_skips_at_email_com(self, tmp_path):
        tracked = _make_repo(tmp_path, {
            "app.py": 'placeholder = "someone@email.com"',
        })
        hits = pocketdev.scan_pii(str(tmp_path), tmp_path, set(tracked))
        emails = [h for h in hits if "Email" in h["type"]]
        assert len(emails) == 0

    def test_skips_short_local_part(self, tmp_path):
        tracked = _make_repo(tmp_path, {
            "test.py": 'x = "ab@domain.com"',
        })
        hits = pocketdev.scan_pii(str(tmp_path), tmp_path, set(tracked))
        emails = [h for h in hits if "Email" in h["type"]]
        assert len(emails) == 0

    def test_skips_noreply_email(self, tmp_path):
        tracked = _make_repo(tmp_path, {
            "git.py": 'author = "bot@users.noreply.github.com"',
        })
        hits = pocketdev.scan_pii(str(tmp_path), tmp_path, set(tracked))
        emails = [h for h in hits if "Email" in h["type"]]
        assert len(emails) == 0

    def test_detects_windows_path(self, tmp_path):
        # The regex matches literal single backslashes: C:\Users\Name
        tracked = _make_repo(tmp_path, {
            "paths.py": 'LOG_DIR = "C:\\Users\\JohnDoe\\logs"',
        })
        hits = pocketdev.scan_pii(str(tmp_path), tmp_path, set(tracked))
        path_hits = [h for h in hits if "path" in h["type"].lower()]
        assert len(path_hits) >= 1

    def test_windows_path_with_expanduser_skipped(self, tmp_path):
        """Paths using expanduser/Path.home/$HOME are code references, not PII leaks."""
        tracked = _make_repo(tmp_path, {
            "paths.py": 'p = expanduser("C:\\Users\\JohnDoe\\Desktop")',
        })
        hits = pocketdev.scan_pii(str(tmp_path), tmp_path, set(tracked))
        path_hits = [h for h in hits if "path" in h["type"].lower()]
        assert len(path_hits) == 0

    def test_detects_phone_with_plus(self, tmp_path):
        tracked = _make_repo(tmp_path, {
            "contact.py": 'phone = "+40 722 123 456"',
        })
        hits = pocketdev.scan_pii(str(tmp_path), tmp_path, set(tracked))
        phone_hits = [h for h in hits if "Phone" in h["type"]]
        assert len(phone_hits) >= 1

    def test_skips_phone_without_plus(self, tmp_path):
        """Phone numbers without + prefix should not be flagged
        (the regex requires it)."""
        tracked = _make_repo(tmp_path, {
            "data.py": 'number = "0722123456"',
        })
        hits = pocketdev.scan_pii(str(tmp_path), tmp_path, set(tracked))
        phone_hits = [h for h in hits if "Phone" in h["type"]]
        assert len(phone_hits) == 0

    def test_skips_pii_ignore_files(self, tmp_path):
        tracked = _make_repo(tmp_path, {
            "package.json": '{"author": "john@realcompany.com"}',
        })
        hits = pocketdev.scan_pii(str(tmp_path), tmp_path, set(tracked))
        assert len(hits) == 0

    def test_skips_non_data_extensions(self, tmp_path):
        tracked = _make_repo(tmp_path, {
            "image.svg": '<text>john@realcompany.com</text>',
        })
        # .svg is not in data_exts, so it should be skipped
        hits = pocketdev.scan_pii(str(tmp_path), tmp_path, set(tracked))
        assert len(hits) == 0


# ---------------------------------------------------------------------------
# find_issues
# ---------------------------------------------------------------------------

class TestFindIssues:
    """Tests for repo health issue detection."""

    def _mock_run_cmd(self, responses):
        """Return a monkeypatched run_cmd that returns canned responses.

        responses: dict mapping command tuples/substrings to (code, stdout, stderr).
        Falls back to (0, "", "") for unknown commands.
        """
        def fake_run_cmd(cmd, timeout=30, cwd=None, cache_key=None):
            if isinstance(cmd, list):
                cmd_str = " ".join(cmd)
            else:
                cmd_str = cmd
            for key, val in responses.items():
                if key in cmd_str:
                    return val
            return (0, "", "")
        return fake_run_cmd

    def test_missing_gitignore(self, tmp_path, monkeypatch):
        # Repo with no .gitignore
        (tmp_path / ".git").mkdir()
        _write(tmp_path / "app.py", "print('hello')")

        repo = {"name": "test", "dir": str(tmp_path), "remote": "https://github.com/x/test.git"}
        all_files = [(tmp_path / "app.py", 100, 1000000)]

        monkeypatch.setattr(pocketdev, "run_cmd", self._mock_run_cmd({
            "ls-files": (0, "app.py", ""),
            "rev-list": (0, "0", ""),
        }))

        issues = pocketdev.find_issues(repo, tmp_path, all_files)
        warnings = issues["warning"]
        assert any("gitignore" in w.lower() for w in warnings)

    def test_missing_readme(self, tmp_path, monkeypatch):
        (tmp_path / ".git").mkdir()
        _write(tmp_path / ".gitignore", "*.pyc")
        _write(tmp_path / "app.py", "print('hello')")

        repo = {"name": "test", "dir": str(tmp_path), "remote": "https://github.com/x/test.git"}
        all_files = [(tmp_path / "app.py", 100, 1000000)]

        monkeypatch.setattr(pocketdev, "run_cmd", self._mock_run_cmd({
            "ls-files": (0, "app.py\n.gitignore", ""),
            "rev-list": (0, "0", ""),
        }))

        issues = pocketdev.find_issues(repo, tmp_path, all_files)
        warnings = issues["warning"]
        assert any("README" in w for w in warnings)

    def test_large_tracked_file_detected(self, tmp_path, monkeypatch):
        (tmp_path / ".git").mkdir()
        _write(tmp_path / ".gitignore", "")
        _write(tmp_path / "README.md", "# Test")
        big_file = tmp_path / "data.csv"
        _write(big_file, "x" * (6 * 1024 * 1024))  # 6MB

        repo = {"name": "test", "dir": str(tmp_path), "remote": "https://github.com/x/test.git"}
        size = big_file.stat().st_size
        all_files = [(big_file, size, 1000000)]

        monkeypatch.setattr(pocketdev, "run_cmd", self._mock_run_cmd({
            "ls-files": (0, "data.csv\n.gitignore\nREADME.md", ""),
            "rev-list": (0, "0", ""),
        }))

        issues = pocketdev.find_issues(repo, tmp_path, all_files)
        warnings = issues["warning"]
        assert any("Large file" in w for w in warnings)

    def test_large_untracked_file_not_flagged(self, tmp_path, monkeypatch):
        (tmp_path / ".git").mkdir()
        _write(tmp_path / ".gitignore", "data.csv")
        _write(tmp_path / "README.md", "# Test")
        big_file = tmp_path / "data.csv"
        _write(big_file, "x" * (6 * 1024 * 1024))

        repo = {"name": "test", "dir": str(tmp_path), "remote": "https://github.com/x/test.git"}
        size = big_file.stat().st_size
        all_files = [(big_file, size, 1000000)]

        # data.csv is NOT in ls-files output
        monkeypatch.setattr(pocketdev, "run_cmd", self._mock_run_cmd({
            "ls-files": (0, ".gitignore\nREADME.md", ""),
            "rev-list": (0, "0", ""),
        }))

        issues = pocketdev.find_issues(repo, tmp_path, all_files)
        warnings = issues["warning"]
        assert not any("Large file" in w and "data.csv" in w for w in warnings)

    def test_no_remote_detected(self, tmp_path, monkeypatch):
        (tmp_path / ".git").mkdir()
        _write(tmp_path / ".gitignore", "")
        _write(tmp_path / "README.md", "# Test")

        repo = {"name": "test", "dir": str(tmp_path), "remote": None}
        all_files = []

        monkeypatch.setattr(pocketdev, "run_cmd", self._mock_run_cmd({
            "ls-files": (0, ".gitignore\nREADME.md", ""),
        }))

        issues = pocketdev.find_issues(repo, tmp_path, all_files)
        warnings = issues["warning"]
        assert any("remote" in w.lower() for w in warnings)


# ---------------------------------------------------------------------------
# parse_backlog
# ---------------------------------------------------------------------------

class TestParseBacklog:
    """Tests for backlog markdown parsing."""

    SAMPLE_BACKLOG = textwrap.dedent("""\
        # Backlog

        ## pocketDEV
        ### [NEW] Add test suite for core scanning functions
        ### [DONE] Rename to pocketDEV

        ## Finance Tracker
        ### [NEW] Add CSV export
        ### [WIP] Fix date parsing bug
    """)

    def test_parses_entries(self, tmp_path):
        path = tmp_path / "_backlog.md"
        path.write_text(self.SAMPLE_BACKLOG, encoding="utf-8")
        entries = pocketdev.parse_backlog(path)
        assert len(entries) == 4

    def test_assigns_tool_names(self, tmp_path):
        path = tmp_path / "_backlog.md"
        path.write_text(self.SAMPLE_BACKLOG, encoding="utf-8")
        entries = pocketdev.parse_backlog(path)
        tools = {e["tool"] for e in entries}
        assert "pocketDEV" in tools
        assert "Finance Tracker" in tools

    def test_parses_status(self, tmp_path):
        path = tmp_path / "_backlog.md"
        path.write_text(self.SAMPLE_BACKLOG, encoding="utf-8")
        entries = pocketdev.parse_backlog(path)
        statuses = {e["status"] for e in entries}
        assert "NEW" in statuses
        assert "DONE" in statuses
        assert "WIP" in statuses

    def test_parses_titles(self, tmp_path):
        path = tmp_path / "_backlog.md"
        path.write_text(self.SAMPLE_BACKLOG, encoding="utf-8")
        entries = pocketdev.parse_backlog(path)
        titles = [e["title"] for e in entries]
        assert "Add test suite for core scanning functions" in titles

    def test_empty_file(self, tmp_path):
        path = tmp_path / "_backlog.md"
        path.write_text("", encoding="utf-8")
        entries = pocketdev.parse_backlog(path)
        assert entries == []

    def test_missing_file(self, tmp_path):
        path = tmp_path / "nonexistent.md"
        entries = pocketdev.parse_backlog(path)
        assert entries == []

    def test_entries_without_tool_header(self, tmp_path):
        md = textwrap.dedent("""\
            ### [NEW] Orphan task
        """)
        path = tmp_path / "_backlog.md"
        path.write_text(md, encoding="utf-8")
        entries = pocketdev.parse_backlog(path)
        assert len(entries) == 1
        assert entries[0]["tool"] == "Unknown"


# ---------------------------------------------------------------------------
# match_repo
# ---------------------------------------------------------------------------

class TestMatchRepo:
    """Tests for repo name matching."""

    REPOS = [
        {"name": "Finance Tracker", "dir": "/a", "remote": None},
        {"name": "pocketDEV", "dir": "/b", "remote": None},
        {"name": "Transcriptor", "dir": "/c", "remote": None},
    ]

    def test_exact_match(self):
        result = pocketdev.match_repo(self.REPOS, "pocketDEV")
        assert len(result) == 1
        assert result[0]["name"] == "pocketDEV"

    def test_case_insensitive(self):
        result = pocketdev.match_repo(self.REPOS, "FINANCE")
        assert len(result) == 1
        assert result[0]["name"] == "Finance Tracker"

    def test_substring_match(self):
        result = pocketdev.match_repo(self.REPOS, "ocket")
        assert len(result) == 1

    def test_no_match(self):
        result = pocketdev.match_repo(self.REPOS, "nonexistent")
        assert len(result) == 0

    def test_multiple_matches(self):
        repos = self.REPOS + [{"name": "Finance v2", "dir": "/d", "remote": None}]
        result = pocketdev.match_repo(repos, "finance")
        assert len(result) == 2


# ---------------------------------------------------------------------------
# get_tracked_files
# ---------------------------------------------------------------------------

class TestGetTrackedFiles:
    """Tests for git tracked file retrieval."""

    def test_returns_tracked_files(self, monkeypatch):
        monkeypatch.setattr(pocketdev, "run_cmd",
                            lambda cmd, **kw: (0, "file1.py\nfile2.js\nREADME.md", ""))
        result = pocketdev.get_tracked_files("/fake/repo")
        assert result == {"file1.py", "file2.js", "README.md"}

    def test_returns_empty_on_failure(self, monkeypatch):
        monkeypatch.setattr(pocketdev, "run_cmd",
                            lambda cmd, **kw: (1, "", "not a git repo"))
        result = pocketdev.get_tracked_files("/fake/repo")
        assert result == set()

    def test_returns_empty_on_empty_output(self, monkeypatch):
        monkeypatch.setattr(pocketdev, "run_cmd",
                            lambda cmd, **kw: (0, "", ""))
        result = pocketdev.get_tracked_files("/fake/repo")
        # "".splitlines() returns [], so set() is empty
        assert result == set()
