---
name: send-email
description: |
  Send an email via Gmail SMTP after human approval. NEVER sends without a file
  in /Approved. Reads the approved REPLY_*.md or EMAIL_*.md file, sends via
  gmail_sender.py, logs the result, and archives to /Done.
  Use this skill when an email approval file appears in /Approved.
---

# Send Email Skill

Send approved emails via Gmail SMTP. Always requires prior human approval.

## Vault Location

The vault is at: `./AI_Employee_Vault`

## MCP Integration

This skill uses `gmail_sender.py` as the external action executor (MCP-style tool).

## Workflow

### Step 1: Check for Approved Emails

```bash
ls AI_Employee_Vault/Approved/REPLY_*.md AI_Employee_Vault/Approved/EMAIL_*.md 2>/dev/null
```

If no approved files exist — **stop**. Do not send anything.

### Step 2: Read the Approved File

For each approved file, read the frontmatter and body:

```bash
cat AI_Employee_Vault/Approved/REPLY_<timestamp>_<subject>.md
```

Extract:
- `to:` — recipient address
- `subject:` — email subject
- `thread_id:` — for replies (optional)
- Email body (everything after the frontmatter)

### Step 3: Send via gmail_sender.py

```bash
python3 gmail_sender.py \
  --to "<recipient>" \
  --subject "<subject>" \
  --body "<email body>" \
  --credentials credentials.json
```

The script uses Gmail API with OAuth2. On first run it will open a browser for auth.

### Step 4: Handle Result

**On success:**
```bash
# Archive the approved file to Done
mv "AI_Employee_Vault/Approved/REPLY_<timestamp>_<subject>.md" \
   "AI_Employee_Vault/Done/DONE_$(date +%Y%m%d_%H%M%S)_SENT_<subject>.md"

# Log
echo '{"timestamp":"<ISO>","action":"email_sent","to":"<recipient>","subject":"<subject>","result":"success"}' \
  >> AI_Employee_Vault/Logs/$(date +%Y-%m-%d).jsonl
```

**On failure:**
```bash
# Move back to Needs_Action with error note
mv "AI_Employee_Vault/Approved/REPLY_<timestamp>_<subject>.md" \
   "AI_Employee_Vault/Needs_Action/FAILED_EMAIL_<timestamp>_<subject>.md"

# Log the error
echo '{"timestamp":"<ISO>","action":"email_failed","to":"<recipient>","subject":"<subject>","error":"<error message>"}' \
  >> AI_Employee_Vault/Logs/$(date +%Y-%m-%d).jsonl
```

### Step 5: Update Dashboard

Run the `update-dashboard` skill.

## gmail_sender.py Setup

The sender script requires:
1. A `credentials.json` file from Google Cloud Console (Gmail API enabled)
2. OAuth2 consent on first run

**To set up:**
1. Go to console.cloud.google.com → APIs & Services → Credentials
2. Create OAuth 2.0 Client ID (Desktop app)
3. Download as `credentials.json` and place in project root
4. First run will open browser for authorization

## Rules

- **NEVER send email without a file in /Approved** — this is absolute
- Always log every send attempt (success or failure)
- If credentials.json is missing, stop and alert the user
- Never store email passwords in plain text — use OAuth2 only
- CC the user on any external email if requested in the approved file
