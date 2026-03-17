---
name: linkedin-post
description: |
  Draft and publish a LinkedIn post with HITL approval workflow.
  Step 1: Generate an engaging post draft and save to /Pending_Approval/LINKEDIN_POST_*.md.
  Step 2: Human reviews — moves file to /Approved to publish, /Rejected to cancel.
  Step 3: linkedin_poster.py detects the approved file and publishes via Playwright.
  Use this skill when the user wants to post on LinkedIn, or when asked to announce
  a milestone, share an update, or generate business leads.
---

# LinkedIn Post Skill (HITL)

Draft → Approve → Auto-publish to LinkedIn.

## Vault Location

The vault is at: `./AI_Employee_Vault`

## Full Workflow

### Step 1: Gather Context

Read relevant context before drafting:

```bash
cat AI_Employee_Vault/Company_Handbook.md
# Also read any brief or task file that triggered this skill
```

### Step 2: Draft the Post

Write an engaging LinkedIn post following this structure:

```
Hook (1 punchy sentence)

Body:
- What was built / achieved (bullet points or short paragraphs)
- Why it matters
- Key insight or lesson learned

Call to action (1 sentence — question or link)

Hashtags (5-10 relevant tags)
```

**Post guidelines:**
- Keep under 1,300 characters for best organic reach
- Lead with a concrete result, not vague claims
- Mention specific tools/tech (Claude Code, Obsidian, MCP, etc.)
- End with a question or CTA to boost engagement
- Include GitHub link if relevant

### Step 3: Save Approval Request

```bash
cat > AI_Employee_Vault/Pending_Approval/LINKEDIN_POST_<slug>_<timestamp>.md << 'EOF'
---
type: approval_request
action: linkedin_post
created: <ISO timestamp>
expires: <ISO timestamp + 24h>
status: pending
skill_to_run: linkedin-post
---

## Proposed LinkedIn Post

---

<Full post text here>

---

## Character count: <N> / 3,000

## To Approve
Move this file to /Approved. linkedin_poster.py will publish automatically.

## To Edit
Edit the post text between the dashes, then move to /Approved.

## To Reject
Move this file to /Rejected.
EOF
```

### Step 4: Start the Poster (if not already running)

```bash
# Watch /Approved continuously (run in a separate terminal)
uv run linkedin_poster.py

# Or check once
uv run linkedin_poster.py --once

# Preview without posting
uv run linkedin_poster.py --dry-run
```

### Step 5: Human Approves

The human moves the file from `/Pending_Approval` to `/Approved`.

`linkedin_poster.py` detects it within 30 seconds and:
1. Extracts the post text
2. Opens LinkedIn via Playwright (saved session from `linkedin_watcher.py --setup`)
3. Clicks "Start a post", types the content, clicks "Post"
4. Takes a screenshot
5. Archives the file to `/Done`
6. Logs the result to `Logs/YYYY-MM-DD.jsonl`

### Step 6: Log and Update Dashboard

After publishing, `linkedin_poster.py` automatically logs:

```json
{"timestamp": "<ISO>", "action": "linkedin_post_published", "file": "<filename>", "chars": <N>, "result": "published"}
```

Then run `update-dashboard` skill to refresh Dashboard.md.

## Approval File Location

```
AI_Employee_Vault/
├── Pending_Approval/LINKEDIN_POST_*.md   ← draft waiting for review
├── Approved/LINKEDIN_POST_*.md           ← approved, poster will publish
├── Rejected/LINKEDIN_POST_*.md           ← rejected, archived
└── Done/DONE_*_PUBLISHED_LINKEDIN_*.md   ← published and archived
```

## Rules

- **NEVER post without a file in /Approved** — this is absolute
- Always save a screenshot of the published post to /Done
- If Playwright can't find the Post button, stop and log the error
- Never fabricate engagement or follower metrics
- Keep the session alive: re-run `uv run linkedin_watcher.py --setup` if session expires
