---
name: request-approval
description: |
  Human-in-the-loop approval workflow. Creates a structured approval request file
  in /Pending_Approval for any sensitive action (email, LinkedIn post, payment,
  deletion, external contact). Monitors /Approved and /Rejected for the human's
  response, then routes to the correct next skill. Use this whenever an action
  requires human sign-off per Company_Handbook.md.
---

# Request Approval Skill

Human-in-the-loop gate for sensitive actions.

## Vault Location

The vault is at: `./AI_Employee_Vault`

## When to Use

Per `Company_Handbook.md`, always use this skill before:
- Sending any email or message
- Posting to LinkedIn or social media
- Any payment action
- Permanently deleting files
- Contacting new individuals
- Processing contracts or invoices

## Workflow

### Step 1: Create Approval Request File

```bash
cat > AI_Employee_Vault/Pending_Approval/APPROVAL_<action_type>_<timestamp>.md << 'EOF'
---
type: approval_request
action: <action_type>
created: <ISO timestamp>
expires: <ISO timestamp + 24h>
priority: high|medium|low
status: pending
skill_to_run: <skill name to invoke after approval>
---

## Action Requested

<Clear description of exactly what will happen if approved>

## Why This Action is Needed

<Reason — what triggered this request>

## What Will Happen

1. <Step 1>
2. <Step 2>
3. ...

## Potential Impact

- **Reversible:** Yes / No
- **External visibility:** Yes (visible to others) / No (internal only)
- **Estimated time:** <duration>

## To Approve

Move this file to `/Approved`. Claude will then run the `<skill_to_run>` skill.

## To Edit

Edit the details above, then move to `/Approved`.

## To Reject

Move this file to `/Rejected`. No action will be taken.
EOF
```

### Step 2: Notify in Dashboard

Immediately run `update-dashboard` so the pending approval shows up in the dashboard count.

### Step 3: Wait for Human Response

Check for response:

```bash
# Check if approved
ls AI_Employee_Vault/Approved/APPROVAL_<action_type>_<timestamp>.md 2>/dev/null

# Check if rejected
ls AI_Employee_Vault/Rejected/APPROVAL_<action_type>_<timestamp>.md 2>/dev/null
```

### Step 4: Route Based on Decision

**If Approved:**
- Read the `skill_to_run` field from the frontmatter
- Invoke that skill (e.g., `send-email`, `linkedin-post`)
- Log: `{"action": "approval_granted", "request": "<file>", "next_skill": "<skill>"}`

**If Rejected:**
- Log: `{"action": "approval_rejected", "request": "<file>", "reason": "human_rejected"}`
- Update Dashboard
- Archive to Done

**If Expired (24h passed, no response):**
- Move to `/Done` with status `expired`
- Log the expiry
- Alert via Dashboard

### Step 5: Log All Outcomes

```bash
echo '{"timestamp":"<ISO>","action":"approval_<outcome>","request_file":"<file>","action_type":"<type>"}' \
  >> AI_Employee_Vault/Logs/$(date +%Y-%m-%d).jsonl
```

## Approval Request Templates

### Email Reply
```yaml
action: send_email_reply
skill_to_run: send-email
```

### LinkedIn Post
```yaml
action: linkedin_post
skill_to_run: linkedin-post
```

### File Deletion
```yaml
action: delete_file
skill_to_run: (none — perform deletion directly after approval)
```

## Rules

- Every approval request must have an `expires` timestamp (24h from creation)
- Never auto-approve anything — the human must physically move the file
- If the same action is requested twice, reference the previous request
- Log every approval, rejection, and expiry
