---
name: linkedin-post
description: |
  Draft and publish a LinkedIn post to generate business leads or share updates.
  Always creates a human approval request first — never posts without explicit approval.
  After approval, uses browsing-with-playwright to log into LinkedIn and publish the post.
  Use this skill when the user wants to post on LinkedIn or when a LINKEDIN_POST task
  appears in /Needs_Action or /Approved.
---

# LinkedIn Post Skill

Draft, approve, and publish LinkedIn posts for business development.

## Vault Location

The vault is at: `./AI_Employee_Vault`

## Workflow

### Step 1: Draft the Post

Read context from:
- `AI_Employee_Vault/Company_Handbook.md` — tone and brand rules
- Any brief or task file in `/Needs_Action` that triggered this skill
- Recent `/Done` files for context on what was accomplished

Write a LinkedIn post draft:

**Post structure:**
```
Hook line (1 sentence — grab attention)

Body (3-5 bullet points or short paragraphs):
- What was built / achieved
- Why it matters
- Key insight or lesson

Call to action (1 sentence)

Relevant hashtags (5-8)
```

### Step 2: Create Approval Request

**LinkedIn posting requires human approval per Company_Handbook.md.**

```bash
cat > AI_Employee_Vault/Pending_Approval/LINKEDIN_POST_<timestamp>.md << 'EOF'
---
type: approval_request
action: linkedin_post
created: <ISO timestamp>
expires: <ISO timestamp + 24h>
status: pending
---

## Proposed LinkedIn Post

<Full post text here>

---

## Character count: <N> / 3000

## To Approve
Move this file to /Approved. The linkedin-post skill will publish it.

## To Edit
Edit the post text above, then move to /Approved.

## To Reject
Move this file to /Rejected.
EOF
```

### Step 3: Watch for Approval

The skill pauses here. When the human moves the file to `/Approved`, proceed to Step 4.

To check:
```bash
ls AI_Employee_Vault/Approved/LINKEDIN_POST_*.md 2>/dev/null
```

### Step 4: Publish via Playwright

Once an approved file exists, use the `browsing-with-playwright` skill to:

1. Navigate to `https://www.linkedin.com`
2. Verify login (if not logged in, stop and ask user to log in manually first)
3. Click "Start a post"
4. Paste the approved post text
5. Click "Post"
6. Take a screenshot for confirmation

```
Use browsing-with-playwright to:
- Go to https://www.linkedin.com/feed/
- Click the "Start a post" button
- Type the post content from the approved file
- Click the Post button
- Take a screenshot of the published post
```

### Step 5: Archive and Log

```bash
# Move approved file to Done
mv "AI_Employee_Vault/Approved/LINKEDIN_POST_<timestamp>.md" \
   "AI_Employee_Vault/Done/DONE_$(date +%Y%m%d_%H%M%S)_LINKEDIN_POST.md"

# Log the action
echo '{"timestamp":"<ISO>","action":"linkedin_post_published","result":"success","approval_required":true}' \
  >> AI_Employee_Vault/Logs/$(date +%Y-%m-%d).jsonl
```

### Step 6: Update Dashboard

Run the `update-dashboard` skill to reflect the completed post.

## Post Content Guidelines

- Lead with a concrete result or insight — no fluff
- Keep it under 1,300 characters for best reach
- Include 5-8 hashtags at the end
- Mention specific technologies used (Claude Code, Obsidian, etc.)
- End with a question or CTA to drive engagement

## Rules

- **NEVER post to LinkedIn without a file in /Approved**
- Always save the screenshot of the published post to `/Done`
- If Playwright cannot find the Post button, stop and alert the user
- Never fabricate engagement metrics
