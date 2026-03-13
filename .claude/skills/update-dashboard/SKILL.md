---
name: update-dashboard
description: |
  Update the AI Employee's Dashboard.md with current vault state: count items
  in each folder, list recent activity from logs, and summarize pending approvals.
  Run this after any vault triage or whenever the dashboard needs refreshing.
---

# Update Dashboard

Refresh `AI_Employee_Vault/Dashboard.md` with the current state of the vault.

## Vault Location

The vault is at: `./AI_Employee_Vault`

## Dashboard Update Workflow

### Step 1: Count Items in Each Folder

```bash
echo "Inbox:            $(ls AI_Employee_Vault/Inbox/ | grep -v '.gitkeep' | wc -l)"
echo "Needs_Action:     $(ls AI_Employee_Vault/Needs_Action/ | grep -v '.gitkeep' | wc -l)"
echo "Pending_Approval: $(ls AI_Employee_Vault/Pending_Approval/ | grep -v '.gitkeep' | wc -l)"
echo "Approved:         $(ls AI_Employee_Vault/Approved/ | grep -v '.gitkeep' | wc -l)"
echo "Done:             $(ls AI_Employee_Vault/Done/ | grep -v '.gitkeep' | wc -l)"
```

### Step 2: Get Recent Activity from Logs

```bash
# Read today's log
today=$(date +%Y-%m-%d)
if [ -f "AI_Employee_Vault/Logs/${today}.jsonl" ]; then
    tail -10 "AI_Employee_Vault/Logs/${today}.jsonl"
fi
```

### Step 3: List Pending Approvals

```bash
ls -la AI_Employee_Vault/Pending_Approval/ 2>/dev/null
```

### Step 4: Write Updated Dashboard.md

Write the following structure to `AI_Employee_Vault/Dashboard.md`:

```markdown
# AI Employee Dashboard

---
last_updated: <current ISO timestamp>
status: active
---

## System Status

| Component | Status | Last Check |
|-----------|--------|------------|
| File System Watcher | ✅ Running | <timestamp> |
| Orchestrator | ✅ Running | <timestamp> |
| Vault Read/Write | ✅ Active | <timestamp> |

## Pending Items

| Folder | Count |
|--------|-------|
| /Inbox | <count> |
| /Needs_Action | <count> |
| /Pending_Approval | <count> |

## Recent Activity

<List last 5 actions from today's log file, formatted as:>
- [HH:MM] <action_type>: <details>

## Business Snapshot

- **Open Tasks:** <needs_action count>
- **Completed This Week:** <done count>
- **Pending Approvals:** <pending_approval count>

---
*Auto-managed by AI Employee · Updated: <timestamp>*
```

## Rules

- Always use the **real current counts** — never fabricate numbers
- If a log file doesn't exist yet, show "No activity today" for Recent Activity
- Keep the last_updated timestamp current (ISO 8601 format)
- The dashboard should be human-readable at a glance
