"""
Tool Auditor — Automated health check for all registered tools.
Scans each tool directory for common issues and generates a plain-language report.
Claude reads the report and proposes improvements.

Usage:
    python audit.py                    # Audit all tools
    python audit.py --tool "Finance"   # Audit one specific tool
    python audit.py --output report.md # Write to file instead of stdout
"""

import json
import os
import subprocess
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path

# Tool registry — must match tool_registry.md
# Format: (name, directory, repo, test_command)
TOOLS = [
    {
        "name": "PFA Accounting Engine",
        "dir": os.path.expanduser("~/Desktop/Claude/Finance"),
        "repo": "vocality-accounting",
        "test_cmd": "cd \"{dir}\" && python _system/_engine/contabilitate.py --help",
        "test_framework": "pytest",
        "test_path": "_system/_engine/tests/",
    },
    {
        "name": "Backup System",
        "dir": os.path.expanduser("~/Desktop/Claude/Backup System"),
        "repo": "claude-backup-system",
        "test_cmd": None,
        "test_framework": None,
        "test_path": None,
    },
    {
        "name": "Preply Lead Auto-Messenger",
        "dir": os.path.expanduser("~/Desktop/Claude/Systems/automations/11-preply-lead-messenger"),
        "repo": "preply-lead-messenger",
        "test_cmd": None,
        "test_framework": "node",
        "test_path": None,
    },
    {
        "name": "Vocality Chat Widget",
        "dir": os.path.expanduser("~/Desktop/Claude/Systems/automations/02-lead-gen-chatbot"),
        "repo": "vocality-chat-widget",
        "test_cmd": None,
        "test_framework": None,
        "test_path": None,
    },
    {
        "name": "Claude Codex (Duolingo)",
        "dir": os.path.expanduser("~/Desktop/Claude/Claude Codex"),
        "repo": "claude-codex",
        "test_cmd": "cd \"{dir}\" && npx vitest run --reporter=verbose 2>&1 | tail -20",
        "test_framework": "vitest",
        "test_path": "src/__tests__/",
    },
    {
        "name": "Vocality Skool",
        "dir": os.path.expanduser("~/Desktop/Claude/Skool"),
        "repo": "vocality-skool",
        "test_cmd": None,
        "test_framework": None,
        "test_path": None,
    },
    {
        "name": "Transcriptor v2",
        "dir": os.path.expanduser("~/Desktop/Transcriptor v2"),
        "repo": "transcriptor-v2",
        "test_cmd": None,
        "test_framework": None,
        "test_path": None,
    },
    {
        "name": "UsageBOT Dashboard",
        "dir": os.path.expanduser("~/Desktop/Claude/UsageBOT"),
        "repo": "claude-code-usage-dashboard",
        "test_cmd": None,
        "test_framework": None,
        "test_path": None,
    },
    {
        "name": "Tool Auditor",
        "dir": os.path.expanduser("~/Desktop/Claude/Tool Auditor"),
        "repo": "claude-tool-auditor",
        "test_cmd": None,
        "test_framework": None,
        "test_path": None,
    },
]


def run_cmd(cmd: str, timeout: int = 30) -> tuple[int, str]:
    """Run a shell command and return (exit_code, output)."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, (result.stdout + result.stderr).strip()
    except subprocess.TimeoutExpired:
        return -1, "TIMEOUT"
    except Exception as e:
        return -1, str(e)


def check_directory(tool: dict) -> dict:
    """Check basic directory health."""
    d = Path(tool["dir"])
    findings = {
        "exists": d.exists(),
        "has_git": (d / ".git").exists(),
        "has_gitignore": (d / ".gitignore").exists(),
        "file_count": 0,
        "total_size_kb": 0,
        "largest_files": [],
        "last_modified": None,
        "uncommitted_changes": 0,
        "unpushed_commits": 0,
    }

    if not d.exists():
        return findings

    # File stats
    all_files = []
    for f in d.rglob("*"):
        if ".git" in f.parts:
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
        # Largest files
        sorted_by_size = sorted(all_files, key=lambda x: x[1], reverse=True)[:5]
        findings["largest_files"] = [
            {"path": str(f.relative_to(d)), "size_kb": s // 1024}
            for f, s, _ in sorted_by_size
        ]

        # Last modified
        most_recent = max(all_files, key=lambda x: x[2])
        findings["last_modified"] = datetime.fromtimestamp(
            most_recent[2], tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M UTC")

    # Git status
    if findings["has_git"]:
        code, output = run_cmd(f'git -C "{d}" status --porcelain')
        if code == 0 and output:
            findings["uncommitted_changes"] = len(output.strip().split("\n"))

        code, output = run_cmd(f'git -C "{d}" log --oneline @{{u}}..HEAD 2>/dev/null')
        if code == 0 and output:
            findings["unpushed_commits"] = len(output.strip().split("\n"))

    return findings


def run_tests(tool: dict) -> dict:
    """Run tests if available."""
    result = {"has_tests": False, "passed": None, "output": None}

    if not tool.get("test_cmd"):
        # Check for common test patterns
        d = Path(tool["dir"])
        if (d / "tests").exists() or (d / "test").exists() or (d / "__tests__").exists():
            result["has_tests"] = True
            result["output"] = "Tests found but no test command configured"
        return result

    result["has_tests"] = True
    cmd = tool["test_cmd"].format(dir=tool["dir"])
    code, output = run_cmd(cmd, timeout=60)
    result["passed"] = code == 0
    result["output"] = output[-500:] if len(output) > 500 else output

    return result


def check_common_issues(tool: dict) -> list[str]:
    """Check for common issues that don't need AI to detect."""
    issues = []
    d = Path(tool["dir"])

    if not d.exists():
        return ["Directory does not exist"]

    # No .gitignore
    if not (d / ".gitignore").exists() and (d / ".git").exists():
        issues.append("No .gitignore file — risk of committing junk files (like node_modules or cache)")

    # node_modules committed
    if (d / "node_modules").exists() and (d / ".git").exists():
        code, output = run_cmd(f'git -C "{d}" ls-files node_modules/ | head -1')
        if code == 0 and output:
            issues.append("node_modules/ is tracked in git — should be in .gitignore (wastes space)")

    # Large files (>5MB)
    for f in d.rglob("*"):
        if ".git" in f.parts:
            continue
        try:
            if f.is_file() and f.stat().st_size > 5 * 1024 * 1024:
                rel = f.relative_to(d)
                size_mb = f.stat().st_size / (1024 * 1024)
                issues.append(f"Large file: {rel} ({size_mb:.1f}MB) — consider .gitignore if not essential")
        except OSError:
            pass

    # No README
    has_readme = any((d / f).exists() for f in ["README.md", "readme.md", "README.txt"])
    if not has_readme and (d / ".git").exists():
        issues.append("No README — makes it hard to remember what this tool does later")

    # Stale (not modified in 30+ days)
    newest = None
    for f in d.rglob("*"):
        if ".git" in f.parts or "node_modules" in f.parts:
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
            issues.append(f"Stale — no files changed in {int(days_since)} days")

    return issues


def audit_tool(tool: dict) -> dict:
    """Run full audit on one tool."""
    return {
        "name": tool["name"],
        "dir": tool["dir"],
        "repo": tool["repo"],
        "directory_check": check_directory(tool),
        "test_results": run_tests(tool),
        "issues": check_common_issues(tool),
    }


def format_report(audits: list[dict]) -> str:
    """Format audit results as a plain-language markdown report."""
    lines = []
    lines.append("# Tool Audit Report")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Tools audited:** {len(audits)}")
    lines.append("")

    total_issues = sum(len(a["issues"]) for a in audits)
    tests_passing = sum(1 for a in audits if a["test_results"]["passed"] is True)
    tests_failing = sum(1 for a in audits if a["test_results"]["passed"] is False)
    tests_none = sum(1 for a in audits if not a["test_results"]["has_tests"])

    lines.append(f"**Quick summary:** {total_issues} issues found. Tests: {tests_passing} passing, {tests_failing} failing, {tests_none} with no tests.")
    lines.append("")

    for audit in audits:
        name = audit["name"]
        dc = audit["directory_check"]
        tr = audit["test_results"]
        issues = audit["issues"]

        # Status emoji-free indicator
        if not dc["exists"]:
            status = "MISSING"
        elif issues:
            status = f"{len(issues)} ISSUE(S)"
        else:
            status = "HEALTHY"

        lines.append(f"---")
        lines.append(f"## {name} — {status}")
        lines.append(f"**Location:** `{audit['dir']}`")
        lines.append(f"**GitHub:** `{audit['repo']}`")
        lines.append("")

        if not dc["exists"]:
            lines.append("Directory does not exist. Tool may have been moved or deleted.")
            lines.append("")
            continue

        # Stats
        lines.append(f"**Files:** {dc['file_count']} | **Size:** {dc['total_size_kb']}KB | **Last changed:** {dc['last_modified']}")

        if dc["uncommitted_changes"]:
            lines.append(f"**Uncommitted changes:** {dc['uncommitted_changes']} file(s) not yet saved to git")
        if dc["unpushed_commits"]:
            lines.append(f"**Unpushed commits:** {dc['unpushed_commits']} commit(s) saved locally but not on GitHub")

        lines.append("")

        # Tests
        if tr["has_tests"]:
            if tr["passed"] is True:
                lines.append(f"**Tests:** PASSING")
            elif tr["passed"] is False:
                lines.append(f"**Tests:** FAILING")
                lines.append(f"```\n{tr['output']}\n```")
            else:
                lines.append(f"**Tests:** {tr['output']}")
        else:
            lines.append("**Tests:** None configured")
        lines.append("")

        # Issues
        if issues:
            lines.append("**Issues found:**")
            for issue in issues:
                lines.append(f"- {issue}")
        else:
            lines.append("**Issues:** None detected")
        lines.append("")

    # Footer for Claude
    lines.append("---")
    lines.append("## For Claude (when processing this report)")
    lines.append("")
    lines.append("Read this report and for each tool with issues, propose fixes in plain language.")
    lines.append("Use the report format from tool_registry.md (TOOL / STATUS / WHAT I FOUND / SUGGESTED IMPROVEMENTS / EFFORT / YOUR CALL).")
    lines.append("Do not fix anything without user approval.")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Audit registered tools for issues")
    parser.add_argument("--tool", type=str, default=None, help="Audit a specific tool by name")
    parser.add_argument("--output", type=str, default=None, help="Write report to file")
    args = parser.parse_args()

    tools_to_audit = TOOLS
    if args.tool:
        tools_to_audit = [t for t in TOOLS if args.tool.lower() in t["name"].lower()]
        if not tools_to_audit:
            print(f"No tool found matching '{args.tool}'", file=sys.stderr)
            sys.exit(1)

    print(f"Auditing {len(tools_to_audit)} tool(s)...", file=sys.stderr)

    audits = []
    for tool in tools_to_audit:
        print(f"  Checking {tool['name']}...", file=sys.stderr)
        audits.append(audit_tool(tool))

    report = format_report(audits)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(report)

    # Write pending flag for Claude to pick up
    pending = Path(__file__).parent / "_audit-pending"
    pending.write_text(datetime.now().strftime('%Y-%m-%d %H:%M'), encoding="utf-8")


if __name__ == "__main__":
    main()
