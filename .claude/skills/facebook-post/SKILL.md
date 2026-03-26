# Skill: facebook-post

Draft and publish a Facebook post with Human-in-the-Loop (HITL) approval workflow.

## Trigger

Use this skill when the user wants to:
- Post something on Facebook
- Announce a milestone, product, or update on Facebook
- Generate business awareness on Facebook/Meta
- When instructed: "post to Facebook", "share on Facebook", "Facebook post about X"

## Workflow

### Step 1 — Draft the post

Write an engaging Facebook post (max 63,206 chars, sweet spot 40–80 words).

Facebook best practices:
- Hook in the first line (Facebook truncates after ~3 lines)
- Conversational tone, slightly more casual than LinkedIn
- Use line breaks for readability
- Add 3–5 relevant hashtags at the end
- Ask a question to boost engagement
- Emojis are encouraged

### Step 2 — Save to /Pending_Approval

Save the draft to:
`AI_Employee_Vault/Pending_Approval/FACEBOOK_POST_<slug>_<YYYYMMDD>.md`

Use this exact format:
```markdown
---
type: facebook_post_draft
platform: Facebook
status: pending_approval
created: <ISO timestamp>
character_count: <N>
---

## Proposed Facebook Post

---
<post text here — exactly what will be published>
---

## Character count
<N> / 63206

## Notes
<any notes for the human reviewer>
```

### Step 3 — Notify human

Tell the user:
> "Your Facebook post draft is ready in `/Pending_Approval/FACEBOOK_POST_*.md`.
> Review it, then move the file to `/Approved` to publish, or `/Rejected` to cancel.
> Run `uv run facebook_poster.py --once` after approving."

### Step 4 — Monitor for approval (if running continuously)

If facebook_poster.py is running in the background, it will auto-detect the approved file and publish it.

After publishing, the file is archived to `/Done/DONE_*_PUBLISHED_FACEBOOK_POST_*.md` and logged.

## Error handling

- If the session is expired, direct user to run: `uv run facebook_poster.py --setup`
- If the post file has no text, log and skip
- Always log every action to `AI_Employee_Vault/Logs/YYYY-MM-DD.jsonl`

## Example invocation

User: "Post about our new AI employee reaching Gold Tier on Facebook"

Claude:
1. Drafts an engaging Facebook post about the Gold Tier milestone
2. Saves to `/Pending_Approval/FACEBOOK_POST_gold_tier_20260326.md`
3. Informs user to review and approve
