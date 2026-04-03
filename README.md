# Claude Tool Auditor

Portable automated health checker for all your git-tracked projects. Scans your machine for git repos, checks for common issues, and generates a plain-language report that Claude can process.

## What it checks

For every git repo it finds:
- Does it have uncommitted changes? Unpushed commits?
- Does it have a .gitignore? A README?
- Are there large files that shouldn't be tracked?
- Is it stale (no changes in 30+ days)?
- Does it have a remote (backed up somewhere)?
- Does it have tests? What framework?

## Requirements

- Python 3.10+
- Git

## Quick Start

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/claude-tool-auditor.git
cd claude-tool-auditor

# Audit everything on your Desktop and Documents
python audit.py

# Audit a specific directory
python audit.py --scan-dir ~/Projects

# Audit repos matching a name
python audit.py --tool "finance"

# Save report to file
python audit.py --output report.md
```

## Scheduling (Weekly)

### Windows
```powershell
$action = New-ScheduledTaskAction -Execute 'C:\Program Files\Git\usr\bin\bash.exe' -Argument '"PATH\TO\run-audit.sh"'
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At '8:00PM'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun
Register-ScheduledTask -TaskName 'Claude Tool Audit' -Action $action -Trigger $trigger -Settings $settings
```

### Linux/macOS
```bash
crontab -e
0 20 * * 0 /path/to/run-audit.sh >> /path/to/audit.log 2>&1
```

## Integration with Claude Code

The auditor writes a `_audit-pending` flag when it completes. If you have a Claude Code SessionStart hook checking for this flag, Claude will notify you that an audit is ready for review.

When you say "review audit", Claude reads the report and proposes fixes in plain language — explaining what each issue means and what to do about it, with no jargon.

## Files

| File | What it does |
|---|---|
| `audit.py` | Main auditor — discovers repos, checks health, generates report |
| `run-audit.sh` | Shell wrapper for scheduling |
