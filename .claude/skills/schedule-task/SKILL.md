---
name: schedule-task
description: |
  Create, list, or remove scheduled tasks using cron (Linux/WSL) or Windows Task
  Scheduler. Use this to automate recurring vault actions — e.g., run gmail_watcher.py
  every 15 minutes, or trigger vault-triage every hour. Use when the user says
  "schedule...", "run every...", "automate...", or "set up a cron job".
---

# Schedule Task Skill

Set up recurring scheduled tasks for the AI Employee system.

## Vault Location

The vault is at: `./AI_Employee_Vault`

## Common Schedules to Set Up

| Task | Recommended Interval | Command |
|------|---------------------|---------|
| Gmail watcher | Every 15 min | `python3 gmail_watcher.py --once` |
| File system watcher | On startup | `python3 watcher.py` (run manually or as service) |
| Vault triage | Every hour | `claude -p "Run vault-triage skill"` |
| Dashboard update | Every 30 min | `claude -p "Run update-dashboard skill"` |

## Workflow

### Step 1: Determine Schedule Type

Check the OS:
```bash
uname -s  # Linux = use cron, Windows = use Task Scheduler
```

### Step 2a: Add a Cron Job (Linux/WSL)

```bash
# View current crontab
crontab -l

# Add new cron job
(crontab -l 2>/dev/null; echo "<cron_expression> <command>") | crontab -

# Examples:
# Every 15 minutes — run gmail watcher once
(crontab -l 2>/dev/null; echo "*/15 * * * * cd /mnt/c/Users/anzal/Desktop/AN-hack-0 && python3 gmail_watcher.py --once >> AI_Employee_Vault/Logs/cron.log 2>&1") | crontab -

# Every hour — run vault triage
(crontab -l 2>/dev/null; echo "0 * * * * cd /mnt/c/Users/anzal/Desktop/AN-hack-0 && claude -p 'Run vault-triage skill' >> AI_Employee_Vault/Logs/cron.log 2>&1") | crontab -

# Every Monday at 8am — CEO briefing
(crontab -l 2>/dev/null; echo "0 8 * * 1 cd /mnt/c/Users/anzal/Desktop/AN-hack-0 && claude -p 'Generate Monday Morning CEO Briefing' >> AI_Employee_Vault/Logs/cron.log 2>&1") | crontab -
```

### Step 2b: Add Windows Task Scheduler (PowerShell)

Run from PowerShell (not WSL):

```powershell
# Every 15 minutes — Gmail watcher
$action = New-ScheduledTaskAction -Execute "python" -Argument "gmail_watcher.py --once" -WorkingDirectory "C:\Users\anzal\Desktop\AN-hack-0"
$trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes 15) -Once -At (Get-Date)
Register-ScheduledTask -TaskName "AIEmployee-GmailWatcher" -Action $action -Trigger $trigger -RunLevel Highest

# Every hour — vault triage
$action2 = New-ScheduledTaskAction -Execute "claude" -Argument "-p 'Run vault-triage skill'" -WorkingDirectory "C:\Users\anzal\Desktop\AN-hack-0"
$trigger2 = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Hours 1) -Once -At (Get-Date)
Register-ScheduledTask -TaskName "AIEmployee-VaultTriage" -Action $action2 -Trigger $trigger2 -RunLevel Highest
```

### Step 3: Verify Schedule

```bash
# Verify cron
crontab -l

# Check cron log
tail -20 AI_Employee_Vault/Logs/cron.log
```

### Step 4: Log the Setup

```bash
echo '{"timestamp":"<ISO>","action":"schedule_created","task":"<task_name>","interval":"<interval>","command":"<command>"}' \
  >> AI_Employee_Vault/Logs/$(date +%Y-%m-%d).jsonl
```

### Step 5: Update Dashboard

Add the schedule to the System Status table in `Dashboard.md`.

## Cron Expression Reference

| Expression | Meaning |
|-----------|---------|
| `*/15 * * * *` | Every 15 minutes |
| `0 * * * *` | Every hour |
| `0 8 * * 1` | Every Monday at 8am |
| `0 9 * * *` | Every day at 9am |
| `0 8 * * 1-5` | Weekdays at 8am |

## Remove a Schedule

```bash
# List all cron jobs
crontab -l

# Remove a specific job (edit crontab)
crontab -e

# Or remove all AI Employee cron jobs
crontab -l | grep -v "AIEmployee\|gmail_watcher\|vault-triage" | crontab -
```

## Rules

- Always log when a schedule is created or removed
- Keep scheduled commands idempotent — safe to run multiple times
- Redirect cron output to `AI_Employee_Vault/Logs/cron.log`
- Don't schedule tasks that require interactive input
