"""
Tool Auditor — Portable automated health check for git-tracked projects.
Auto-discovers all git repos in configured scan directories,
checks for common issues, and generates a plain-language report.

Works on any machine. No hardcoded paths.

Usage:
    python audit.py                          # Audit all discovered repos
    python audit.py --tool "Finance"         # Audit repos matching a name
    python audit.py --scan-dir ~/Projects    # Scan a specific directory
    python audit.py --output report.md       # Write to file
"""

import json
import os
import subprocess
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path


def find_git_repos(scan_dirs: list[str], max_depth: int = 4) -> list[dict]:
    """Auto-discover all git repos with remotes in the given directories."""
    repos = []
    seen_paths = set()

    for scan_dir in scan_dirs:
        d = Path(os.path.expanduser(scan_dir))
        if not d.exists():
            continue

        # Walk directory tree looking for .git folders
        for root, dirs, files in os.walk(d):
            # Respect max depth
            depth = len(Path(root).relative_to(d).parts)
            if depth > max_depth:
                dirs.clear()
                continue

            # Skip inside .git, node_modules, etc.
            dirs[:] = [
                x for x in dirs
                if x not in {".git", "node_modules", "__pycache__", "venv", ".venv", "dist", "build"}
            ]

            git_dir = Path(root) / ".git"
            if git_dir.exists() and git_dir.is_dir():
                repo_path = Path(root)
                real_path = str(repo_path.resolve())

                if real_path in seen_paths:
                    continue
                seen_paths.add(real_path)

                # Get remote URL
                try:
                    result = subprocess.run(
                        ["git", "-C", str(repo_path), "remote", "get-url", "origin"],
                        capture_output=True, text=True, timeout=5
                    )
                    remote = result.stdout.strip() if result.returncode == 0 else None
                except Exception:
                    remote = None

                # Extract repo name from remote URL or folder name
                repo_name = repo_path.name
                if remote:
                    # Extract from URLs like https://github.com/user/repo.git
                    parts = remote.rstrip("/").rstrip(".git").split("/")
                    if len(parts) >= 2:
                        repo_name = parts[-1]

                repos.append({
                    "name": repo_path.name,
                    "dir": str(repo_path),
                    "repo": repo_name,
                    "remote": remote,
                })

                # Don't descend into repos (skip nested .git)
                dirs.clear()

    return sorted(repos, key=lambda r: r["name"].lower())


def run_cmd(cmd: str | list, timeout: int = 30, cwd: str = None) -> tuple[int, str]:
    """Run a command and return (exit_code, output)."""
    try:
        if isinstance(cmd, str):
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=cwd
            )
        else:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd
            )
        return result.returncode, (result.stdout + result.stderr).strip()
    except subprocess.TimeoutExpired:
        return -1, "TIMEOUT"
    except Exception as e:
        return -1, str(e)


def check_directory(repo: dict) -> dict:
    """Check basic directory health."""
    d = Path(repo["dir"])
    findings = {
        "exists": d.exists(),
        "has_gitignore": (d / ".gitignore").exists(),
        "file_count": 0,
        "total_size_kb": 0,
        "largest_files": [],
        "last_modified": None,
        "uncommitted_changes": 0,
        "unpushed_commits": 0,
        "has_remote": repo["remote"] is not None,
    }

    if not d.exists():
        return findings

    # File stats (skip .git and node_modules)
    all_files = []
    skip_dirs = {".git", "node_modules", "__pycache__", "venv", ".venv", "dist", "build"}
    for f in d.rglob("*"):
        if any(part in skip_dirs for part in f.parts):
            continue
        if f.is_file():
            try:
                size = f.stat().st_size
                mtime = f.stat().st_mtime
                all_files.append((f, size, mtime))
            except OSError:
                pass

    findings["file_count"] = len(all_files)
    findings["total_size_kb"] = sum(s for _, s, _ in all_files) // 1024

    if all_files:
        sorted_by_size = sorted(all_files, key=lambda x: x[1], reverse=True)[:5]
        findings["largest_files"] = [
            {"path": str(f.relative_to(d)), "size_kb": s // 1024}
            for f, s, _ in sorted_by_size
        ]
        most_recent = max(all_files, key=lambda x: x[2])
        findings["last_modified"] = datetime.fromtimestamp(
            most_recent[2], tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M UTC")

    # Git status
    code, output = run_cmd(["git", "status", "--porcelain"], cwd=repo["dir"])
    if code == 0 and output:
        findings["uncommitted_changes"] = len(output.strip().split("\n"))

    code, output = run_cmd(["git", "log", "--oneline", "@{u}..HEAD"], cwd=repo["dir"])
    if code == 0 and output:
        findings["unpushed_commits"] = len(output.strip().split("\n"))

    return findings


def detect_tests(repo: dict) -> dict:
    """Detect and optionally run tests."""
    d = Path(repo["dir"])
    result = {"has_tests": False, "framework": None, "passed": None, "output": None}

    # Detect test framework
    if (d / "package.json").exists():
        try:
            pkg = json.loads((d / "package.json").read_text(encoding="utf-8"))
            scripts = pkg.get("scripts", {})
            if "test" in scripts and scripts["test"] != 'echo "Error: no test specified" && exit 1':
                result["has_tests"] = True
                result["framework"] = "npm test"
        except (json.JSONDecodeError, OSError):
            pass

    if any(d.rglob("test_*.py")) or any(d.rglob("*_test.py")) or (d / "tests").exists():
        result["has_tests"] = True
        result["framework"] = "pytest"

    if any(d.rglob("*.test.js")) or any(d.rglob("*.spec.js")):
        result["has_tests"] = True
        result["framework"] = result["framework"] or "jest/vitest"

    return result


def check_common_issues(repo: dict) -> list[str]:
    """Check for common issues."""
    issues = []
    d = Path(repo["dir"])

    if not d.exists():
        return ["Directory does not exist"]

    if not (d / ".gitignore").exists():
        issues.append("No .gitignore — risk of committing junk files")

    # node_modules tracked in git
    if (d / "node_modules").exists():
        code, output = run_cmd(["git", "ls-files", "node_modules/"], cwd=repo["dir"])
        if code == 0 and output:
            issues.append("node_modules/ is tracked in git — add to .gitignore")

    # Large files (>5MB, excluding .git)
    skip_dirs = {".git", "node_modules", "__pycache__"}
    for f in d.rglob("*"):
        if any(part in skip_dirs for part in f.parts):
            continue
        try:
            if f.is_file() and f.stat().st_size > 5 * 1024 * 1024:
                rel = f.relative_to(d)
                size_mb = f.stat().st_size / (1024 * 1024)
                issues.append(f"Large file: {rel} ({size_mb:.1f}MB)")
        except OSError:
            pass

    # No README
    has_readme = any((d / f).exists() for f in ["README.md", "readme.md", "README.txt", "README"])
    if not has_readme:
        issues.append("No README")

    # Stale (not modified in 30+ days)
    newest = None
    for f in d.rglob("*"):
        if any(part in skip_dirs for part in f.parts):
            continue
        try:
            if f.is_file():
                mtime = f.stat().st_mtime
                if newest is None or mtime > newest:
                    newest = mtime
        except OSError:
            pass

    if newest:
        days_since = (datetime.now().timestamp() - newest) / 86400
        if days_since > 30:
            issues.append(f"Stale — no changes in {int(days_since)} days")

    # No remote
    if not repo["remote"]:
        issues.append("No git remote — not backed up anywhere")

    return issues


def format_report(audits: list[dict]) -> str:
    """Format audit results as plain-language markdown."""
    lines = []
    lines.append("# Tool Audit Report")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Tools audited:** {len(audits)}")
    lines.append("")

    total_issues = sum(len(a["issues"]) for a in audits)
    with_tests = sum(1 for a in audits if a["tests"]["has_tests"])
    lines.append(f"**Quick summary:** {total_issues} issues found across {len(audits)} repos. {with_tests} have tests configured.")
    lines.append("")

    for audit in audits:
        dc = audit["directory"]
        tr = audit["tests"]
        issues = audit["issues"]

        if not dc["exists"]:
            status = "MISSING"
        elif issues:
            status = f"{len(issues)} ISSUE(S)"
        else:
            status = "HEALTHY"

        lines.append(f"---")
        lines.append(f"## {audit['name']} — {status}")
        lines.append(f"**Location:** `{audit['dir']}`")
        if audit.get("remote"):
            lines.append(f"**Remote:** `{audit['remote']}`")
        lines.append("")

        if not dc["exists"]:
            lines.append("Directory does not exist.")
            continue

        lines.append(f"**Files:** {dc['file_count']} | **Size:** {dc['total_size_kb']}KB | **Last changed:** {dc['last_modified']}")

        if dc["uncommitted_changes"]:
            lines.append(f"**Uncommitted:** {dc['uncommitted_changes']} file(s)")
        if dc["unpushed_commits"]:
            lines.append(f"**Unpushed:** {dc['unpushed_commits']} commit(s)")

        lines.append("")

        if tr["has_tests"]:
            lines.append(f"**Tests:** {tr['framework']}")
        else:
            lines.append("**Tests:** None detected")

        if issues:
            lines.append("\n**Issues:**")
            for issue in issues:
                lines.append(f"- {issue}")
        else:
            lines.append("**Issues:** None")
        lines.append("")

    lines.append("---")
    lines.append("## For Claude")
    lines.append("For each tool with issues, propose fixes in plain language.")
    lines.append("Format: TOOL / STATUS / WHAT I FOUND / SUGGESTED IMPROVEMENTS / EFFORT / YOUR CALL")
    lines.append("Do not fix anything without user approval.")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Audit git repos for issues (portable)")
    parser.add_argument("--tool", type=str, default=None, help="Filter repos by name")
    parser.add_argument("--scan-dir", type=str, action="append", help="Directory to scan (repeatable)")
    parser.add_argument("--output", type=str, default=None, help="Write report to file")
    args = parser.parse_args()

    scan_dirs = args.scan_dir or [
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~/Documents"),
        os.path.expanduser("~/Projects"),
    ]

    print(f"Scanning for git repos in: {', '.join(scan_dirs)}", file=sys.stderr)
    repos = find_git_repos(scan_dirs)

    if args.tool:
        repos = [r for r in repos if args.tool.lower() in r["name"].lower()]

    if not repos:
        print("No git repos found.", file=sys.stderr)
        sys.exit(0)

    print(f"Found {len(repos)} repo(s). Auditing...", file=sys.stderr)

    audits = []
    for repo in repos:
        print(f"  {repo['name']}...", file=sys.stderr)
        audits.append({
            "name": repo["name"],
            "dir": repo["dir"],
            "remote": repo["remote"],
            "directory": check_directory(repo),
            "tests": detect_tests(repo),
            "issues": check_common_issues(repo),
        })

    report = format_report(audits)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"Report: {args.output}", file=sys.stderr)
    else:
        print(report)

    # Write pending flag
    pending = Path(__file__).parent / "_audit-pending"
    pending.write_text(datetime.now().strftime('%Y-%m-%d %H:%M'), encoding="utf-8")


if __name__ == "__main__":
    main()
