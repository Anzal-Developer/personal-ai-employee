---
name: process-file-drop
description: |
  Process new files that have been dropped into the vault's /Inbox or /Needs_Action
  folder by the File System Watcher. Read the companion .md metadata file, determine
  the appropriate action based on Company_Handbook.md, create a plan if needed,
  and route the item to the correct next state. Use this when the filesystem watcher
  has created new DROP_*.md files in /Needs_Action.
---

# Process File Drop

Handle files that the File System Watcher has detected and placed in the vault.

## Vault Location

The vault is at: `./AI_Employee_Vault`

## What the Watcher Creates

When a file is dropped into `./Drop/`, the filesystem watcher creates:
1. `AI_Employee_Vault/Needs_Action/DROP_<timestamp>_<filename>` — copy of the file
2. `AI_Employee_Vault/Needs_Action/DROP_<timestamp>_<filename>.md` — metadata + instructions

## Processing Workflow

### Step 1: Find Unprocessed Drop Files

```bash
ls AI_Employee_Vault/Needs_Action/DROP_*.md 2>/dev/null
```

### Step 2: Read Each Metadata File

For each `DROP_*.md` file found:
1. Read the full content including YAML frontmatter
2. Note the `type`, `original_name`, `size_bytes`, and `priority`
3. Read `Company_Handbook.md` to determine allowed actions

### Step 3: Classify File Type and Determine Action

Based on the file extension and content, decide:

| File Type | Auto Action | Notes |
|-----------|-------------|-------|
| `.txt` / `.md` | Read, summarize, log | Safe to process autonomously |
| `.pdf` | Note received, await instruction | Flag for human review |
| `.csv` | Parse for data insights | Can auto-summarize |
| `.docx` / `.xlsx` | Note received | Flag for human review |
| Invoice / contract keywords | Create approval request | Never process autonomously |
| Unknown | Move to /Pending_Approval | Caution by default |

### Step 4: For Safe Files — Process Autonomously

```bash
# Example: summarize a text file
cat "AI_Employee_Vault/Needs_Action/DROP_<timestamp>_<filename>"
```

Create a brief note in the companion `.md` file:
- What the file contains
- What action was taken
- Any follow-up recommended

Then move to Done:
```bash
mv "AI_Employee_Vault/Needs_Action/DROP_<timestamp>_<filename>.md" \
   "AI_Employee_Vault/Done/DONE_<timestamp>_DROP_<filename>.md"
mv "AI_Employee_Vault/Needs_Action/DROP_<timestamp>_<filename>" \
   "AI_Employee_Vault/Done/"
```

### Step 5: For Sensitive Files — Create Approval Request

```bash
cat > AI_Employee_Vault/Pending_Approval/APPROVAL_file_<timestamp>.md << 'EOF'
---
type: approval_request
action: process_sensitive_file
file: <original_filename>
created: <timestamp>
status: pending
---

## File Received

A potentially sensitive file was dropped and requires your review before processing.

**File:** `<filename>`
**Size:** <size> bytes
**Type:** <detected type>

## Suggested Action
<What Claude thinks should be done>

## To Approve
Move this file to /Approved.

## To Reject
Move this file to /Rejected.
EOF
```

### Step 6: Update Dashboard

After processing all drop files, refresh the dashboard:
- Update the Needs_Action and Done counts
- Log the action in today's `Logs/YYYY-MM-DD.jsonl` file

## Rules

- Always read `Company_Handbook.md` before deciding what to do with a file
- Never read or process files with sensitive keywords without human approval
- Keep the original file in /Done after processing (do not delete)
- Log every action taken to `Logs/YYYY-MM-DD.jsonl`
