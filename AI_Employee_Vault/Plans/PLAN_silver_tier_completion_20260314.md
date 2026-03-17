---
created: 2026-03-14T05:00:00Z
task_source: user_request
objective: Complete Silver Tier — all requirements working end-to-end
priority: high
estimated_steps: 6
approval_required: true
status: in_progress
---

## Objective

Complete Silver Tier of the Personal AI Employee Hackathon. All 6 requirements must be demonstrated working end-to-end.

## Silver Tier Requirements

1. All Bronze requirements ✅
2. Two+ watcher scripts (file system ✅ + Gmail)
3. LinkedIn auto-post (draft → approval → publish)
4. Claude reasoning loop creating Plan.md files
5. One working MCP server for external action (Gmail send)
6. Human-in-the-loop approval workflow
7. Basic scheduling via cron
8. All AI functionality as Agent Skills ✅

## Steps

- [x] **Step 1:** Install Gmail API dependencies (google-auth, google-api-python-client)
- [~] **Step 2:** Test Gmail watcher — run `gmail_watcher.py --once`, verify emails route to Needs_Action/
- [ ] **Step 3:** Run `gmail-watcher` skill to process emails from inbox — *autonomous*
- [ ] **Step 4:** Create LinkedIn post draft → create approval request in /Pending_Approval — *requires approval*
- [ ] **Step 5:** Set up cron schedule for gmail_watcher (every 15 min) + vault-triage (every hour) — *autonomous*
- [ ] **Step 6:** Update Dashboard with Silver Tier system status — *autonomous*

## Approval Gates

- Step 4: LinkedIn post requires human approval before publishing

## Completion Criteria

- Gmail watcher polls inbox and creates GMAIL_*.md files in Needs_Action/
- gmail-watcher skill processes those emails
- LinkedIn post approval request visible in Pending_Approval/
- Cron jobs scheduled and verified
- Dashboard shows all Silver Tier components as active
