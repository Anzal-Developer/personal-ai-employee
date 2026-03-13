---
name: vault-triage
description: |
  Process all pending items in the AI Employee vault's /Needs_Action folder.
  For each item: read it, consult Company_Handbook.md, create a Plan.md if
  multi-step, take permitted autonomous actions, create approval files for
  sensitive actions, and move the task to /Done when complete.
  Use this skill whenever there are unprocessed items in /Needs_Action.
---

# Vault Triage

Process pending tasks in the AI Employee Obsidian vault.

## Vault Location

The vault is at: `./AI_Employee_Vault`

## Triage Workflow

### Step 1: Read the Handbook

Before processing any task, always read the rules:

```bash
cat AI_Employee_Vault/Company_Handbook.md
```

### Step 2: List Pending Items

```bash
ls -la AI_Employee_Vault/Needs_Action/
```

Count and list all `.md` files (skip `.gitkeep`).

### Step 3: Process Each Item

For each `.md` file in `/Needs_Action`:

1. **Read** the action file to understand what is needed
2. **Classify** the priority (high / medium / low) from the frontmatter
3. **Decide** the action based on `Company_Handbook.md` rules:
   - If autonomous action allowed → act and move to `/Done`
   - If approval required → create file in `/Pending_Approval` and update Dashboard

### Step 4: Create a Plan (multi-step tasks)

If a task has 3+ steps, write a plan first:

```bash
# Create plan file
cat > AI_Employee_Vault/Plans/PLAN_<task_name>_<timestamp>.md << 'EOF'
---
created: <ISO timestamp>
task_source: <source file name>
status: in_progress
---

## Objective
<What needs to be accomplished>

## Steps
- [ ] Step 1
- [ ] Step 2
- [ ] Step 3

## Completion Criteria
<What defines "done">
EOF
```

### Step 5: Handle Approval-Required Items

For any action requiring human approval per Company_Handbook.md:

```bash
cat > AI_Employee_Vault/Pending_Approval/APPROVAL_<action>_<timestamp>.md << 'EOF'
---
type: approval_request
action: <action type>
created: <ISO timestamp>
expires: <ISO timestamp + 24h>
status: pending
---

## Action Requested
<Description of what Claude wants to do>

## Reason
<Why this action is needed>

## To Approve
Move this file to /Approved folder.

## To Reject
Move this file to /Rejected folder.
EOF
```

### Step 6: Move Completed Tasks to /Done

```bash
mv "AI_Employee_Vault/Needs_Action/<task_file>" \
   "AI_Employee_Vault/Done/DONE_$(date +%Y%m%d_%H%M%S)_<task_file>"
```

### Step 7: Update Dashboard

After processing all items, run the `update-dashboard` skill to refresh `Dashboard.md`.

## Priority Rules

| Priority | Handle First | Auto-Act? |
|----------|-------------|-----------|
| high     | Yes          | If permitted by handbook |
| medium   | After high   | If permitted by handbook |
| low      | After medium | If permitted by handbook |

## What Claude Can Do Autonomously

Per `Company_Handbook.md`:
- Read and organize files
- Create plans and draft documents
- Move files between internal vault folders
- Update Dashboard.md and logs
- Generate briefing documents

## What Requires Approval

- Sending emails or messages
- Any payment action
- Social media posts
- Deleting files
- Contacting new individuals
