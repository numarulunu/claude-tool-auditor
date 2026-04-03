# pocketDEV

Senior developer on call. Audits, reviews, and diagnoses your git-tracked projects.

## Modes

| Mode | What it does |
|---|---|
| `audit` | Health scan across all repos — missing .gitignore, large files, stale code, no tests, uncommitted work |
| `review <tool>` | Deep code quality dive — complexity hotspots, TODOs, secrets, dependency health, test coverage |
| `diagnose <tool>` | Broken tool triage — runs tests, checks recent changes, reads logs, verifies dependencies |

## Requirements

- Python 3.10+
- Git

## Usage

```bash
# Audit everything
python pocketdev.py audit

# Audit one tool
python pocketdev.py audit --tool "Finance"

# Deep review
python pocketdev.py review "Finance"

# Diagnose a broken tool
python pocketdev.py diagnose "Transcriptor"

# Custom scan directory
python pocketdev.py --scan-dir ~/Projects audit

# Save report to file
python pocketdev.py audit --output report.md
```

## Shell Wrapper

```bash
./run-pocketdev.sh audit                    # Audit all
./run-pocketdev.sh audit "Finance"          # Audit one
./run-pocketdev.sh review "Finance"         # Deep review
./run-pocketdev.sh diagnose "Transcriptor"  # Diagnose
```

## Scheduling (Weekly Audit)

### Windows
```powershell
$action = New-ScheduledTaskAction -Execute 'C:\Program Files\Git\usr\bin\bash.exe' -Argument '"C:\path\to\run-pocketdev.sh" audit'
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At '8:00PM'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun
Register-ScheduledTask -TaskName 'pocketDEV Audit' -Action $action -Trigger $trigger -Settings $settings
```

### Linux/macOS
```bash
0 20 * * 0 /path/to/run-pocketdev.sh audit >> /path/to/pocketdev.log 2>&1
```

## Integration with Claude Code

pocketDEV writes a `_audit-pending` flag after each audit. A Claude Code SessionStart hook checks for this flag and prompts you to review results.

When you say "review audit", Claude reads the report as pocketDEV — a senior developer presenting findings with concrete fixes, effort estimates, and priorities.

## Files

| File | What it does |
|---|---|
| `pocketdev.py` | Main tool — audit, review, diagnose modes |
| `run-pocketdev.sh` | Shell wrapper for scheduling and manual runs |
| `CLAUDE.md` | System instructions — tells Claude how to act as pocketDEV |
