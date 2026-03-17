---
name: gmail-watcher
description: |
  Process new Gmail messages that the gmail_watcher.py script has routed into
  AI_Employee_Vault/Needs_Action/ as GMAIL_*.md files. Read each email summary,
  classify priority and intent, decide the correct action per Company_Handbook.md,
  draft a reply or approval request, and move to Done when complete.
  Use this skill when GMAIL_*.md files appear in /Needs_Action.
---

# Gmail Watcher Skill

Process emails captured by `gmail_watcher.py` and routed into the vault.

## Vault Location

The vault is at: `./AI_Employee_Vault`

## What the Gmail Watcher Creates

When a new unread email is detected, `gmail_watcher.py` creates:

`AI_Employee_Vault/Needs_Action/GMAIL_<timestamp>_<subject_slug>.md`

With frontmatter:
```yaml
---
type: gmail
from: sender@example.com
subject: "Email subject"
received_at: 2026-03-14T10:00:00Z
snippet: "First 200 chars of email body..."
thread_id: "abc123"
message_id: "xyz789"
priority: high|medium|low
status: pending
---
```

## Processing Workflow

### Step 1: Read the Handbook

```bash
cat AI_Employee_Vault/Company_Handbook.md
```

### Step 2: List Gmail Items

```bash
ls AI_Employee_Vault/Needs_Action/GMAIL_*.md 2>/dev/null
```

### Step 3: Classify Each Email

For each `GMAIL_*.md` file:

| Signal | Priority |
|--------|----------|
| From known contacts, urgent keywords | high |
| Business inquiry, project update | medium |
| Newsletter, notification | low |
| Invoice, contract, payment | high + approval required |

### Step 4: Decide Action

| Email Type | Action |
|------------|--------|
| Question / inquiry | Draft reply → create APPROVAL in /Pending_Approval |
| Invoice / payment | Create approval request — never auto-process |
| Newsletter / notification | Summarize and move to Done |
| Task assignment | Create task file in /Needs_Action |
| Unknown sender | Flag for human review |

### Step 5: Draft Reply (if needed)

Write a draft reply to `AI_Employee_Vault/Pending_Approval/REPLY_<timestamp>_<subject>.md`:

```markdown
---
type: approval_request
action: send_email_reply
to: sender@example.com
subject: Re: <original subject>
thread_id: <thread_id>
created: <ISO timestamp>
expires: <ISO timestamp + 24h>
status: pending
---

## Proposed Reply

<Draft email body here>

## To Approve
Move this file to /Approved. The send-email skill will send it.

## To Reject
Move this file to /Rejected.
```

### Step 6: Move to Done

```bash
mv "AI_Employee_Vault/Needs_Action/GMAIL_<timestamp>_<slug>.md" \
   "AI_Employee_Vault/Done/DONE_$(date +%Y%m%d_%H%M%S)_GMAIL_<slug>.md"
```

### Step 7: Log and Update Dashboard

```bash
echo '{"timestamp":"<ISO>","action":"gmail_processed","from":"<sender>","subject":"<subject>","result":"<action taken>","approval_required":<bool>}' \
  >> AI_Employee_Vault/Logs/$(date +%Y-%m-%d).jsonl
```

Then run the `update-dashboard` skill.

## Rules

- **Never send a reply without human approval** — always create an approval request
- Summarize newsletter/notification emails autonomously
- Always log every email processed
- Flag any email mentioning payment, invoice, legal, or contract as high priority
