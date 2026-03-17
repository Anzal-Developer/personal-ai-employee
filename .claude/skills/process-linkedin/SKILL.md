---
name: process-linkedin
description: |
  Process LinkedIn notifications and messages routed by linkedin_watcher.py into
  AI_Employee_Vault/Needs_Action/ as LINKEDIN_*.md files. Classify each item,
  draft replies for messages (with approval), summarize notifications autonomously,
  and move to Done. Use this skill when LINKEDIN_*.md files appear in /Needs_Action.
---

# Process LinkedIn Skill

Handle LinkedIn items captured by `linkedin_watcher.py`.

## Vault Location

The vault is at: `./AI_Employee_Vault`

## What the LinkedIn Watcher Creates

`AI_Employee_Vault/Needs_Action/LINKEDIN_<timestamp>_<slug>.md`

With frontmatter:
```yaml
---
type: linkedin_message | linkedin_notification
from: Sender Name
subject: "Subject or preview"
received_at: 2026-03-17T10:00:00Z
snippet: "Message preview..."
item_id: "unique-id"
priority: high|medium|low
status: pending
---
```

## Processing Workflow

### Step 1: Read the Handbook

```bash
cat AI_Employee_Vault/Company_Handbook.md
```

### Step 2: List LinkedIn Items

```bash
ls AI_Employee_Vault/Needs_Action/LINKEDIN_*.md 2>/dev/null
```

### Step 3: Classify Each Item

| Type | Signal | Action |
|------|--------|--------|
| `linkedin_message` | Direct message from a person | Draft reply → Pending_Approval |
| `linkedin_message` | Sales pitch / spam | Summarize and move to Done |
| `linkedin_notification` | Connection accepted | Note and move to Done |
| `linkedin_notification` | Post engagement (likes, comments) | Summarize and move to Done |
| `linkedin_notification` | Job alert | Note and move to Done |
| `linkedin_notification` | Urgent / mentions you | Create task in Needs_Action |

### Step 4: For Messages — Draft Reply

Write a draft reply to `AI_Employee_Vault/Pending_Approval/REPLY_LINKEDIN_<timestamp>.md`:

```markdown
---
type: approval_request
action: linkedin_reply
from: <sender>
subject: "Re: <original subject>"
item_id: <item_id>
created: <ISO timestamp>
expires: <ISO timestamp + 24h>
status: pending
skill_to_run: browsing-with-playwright
---

## Original Message
<snippet from the LinkedIn message>

## Proposed Reply

<Draft reply here — professional, concise>

## To Approve
Move this file to /Approved. Use browsing-with-playwright to send via LinkedIn.

## To Reject
Move this file to /Rejected.
```

### Step 5: Move to Done

```bash
mv "AI_Employee_Vault/Needs_Action/LINKEDIN_<timestamp>_<slug>.md" \
   "AI_Employee_Vault/Done/DONE_$(date +%Y%m%d_%H%M%S)_LINKEDIN_<slug>.md"
```

### Step 6: Log and Update Dashboard

```bash
echo '{"timestamp":"<ISO>","action":"linkedin_processed","from":"<sender>","type":"<type>","result":"<action>","approval_required":<bool>}' \
  >> AI_Employee_Vault/Logs/$(date +%Y-%m-%d).jsonl
```

Run `update-dashboard` skill.

## Rules

- **Never send a LinkedIn reply without human approval**
- Notifications (likes, views, follows) are always safe to process autonomously
- Direct messages from real people always need a reply draft + approval
- Log every item processed
