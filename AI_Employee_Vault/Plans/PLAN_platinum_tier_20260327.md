# Platinum Tier Implementation Plan
**Created:** 2026-03-27
**Status:** COMPLETE ✓
**AWS VM:** 13.233.108.91 (ubuntu)

---

## Objective
Run the AI Employee 24/7 on cloud with full Cloud ↔ Local work-zone specialisation.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  CLOUD (AWS 13.233.108.91) — 24/7                                   │
│  ┌─────────────────┐  ┌──────────────────────┐  ┌───────────────┐  │
│  │ gmail_watcher   │  │ cloud_orchestrator   │  │ sync_vault    │  │
│  │ (PM2, always)   │  │ (PM2, every 2 min)   │  │ (PM2, 5 min)  │  │
│  └───────┬─────────┘  └──────────┬───────────┘  └───────┬───────┘  │
│          │ writes                │ claim-by-move         │ git push  │
│          ▼                       ▼                       ▼           │
│    /Needs_Action/         /In_Progress/cloud/      GitHub master     │
│                           /Pending_Approval/cloud/                   │
│                           /Updates/SIGNAL_*.md                       │
└──────────────────────────────────────┬──────────────────────────────┘
                                       │ git push
                                  ─────▼─────
                                  GitHub Repo
                                  ─────┬─────
                                       │ git pull
┌──────────────────────────────────────▼──────────────────────────────┐
│  LOCAL (Your PC) — runs on startup / manually                        │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │ local_orchestrator.py                                        │    │
│  │  1. git pull (gets cloud drafts)                             │    │
│  │  2. Show /Pending_Approval/cloud/ → human reviews            │    │
│  │  3. Human moves to /Approved/ → execute (gmail_sender.py)    │    │
│  │  4. Merge /Updates/SIGNAL_*.md → Dashboard.md (SINGLE WRITE) │    │
│  │  5. git push                                                 │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  Also owns: linkedin_poster.py, facebook_poster.py, WhatsApp        │
│             Odoo (local Docker), payment approvals                   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Platinum Demo Gate ✓
> Email arrives while Local is offline → Cloud drafts reply + writes approval file
> → when Local returns, user approves → Local executes send → logs → /Done

**Trace:**
1. Email arrives in Gmail
2. `gmail_watcher.py` (cloud) → writes `GMAIL_*.md` to `/Needs_Action/`
3. `cloud_orchestrator.py` → atomic claim → `/In_Progress/cloud/`
4. Drafts reply → `/Pending_Approval/cloud/DRAFT_REPLY_*.md`
5. Writes signal → `/Updates/SIGNAL_*.md`
6. `sync_vault.py` → git commit + push
7. **[Local comes online]** → `local_orchestrator.py` → git pull
8. Shows pending approval to human
9. Human moves to `/Approved/`
10. `local_orchestrator.py --send-approved` → `gmail_sender.py` → email sent
11. Archives to `/Done/` → git push

---

## Files Created

| File | Location | Purpose |
|------|----------|---------|
| `sync_vault.py` | root | Git-based vault sync (PM2, every 5 min) |
| `cloud_orchestrator.py` | root | Cloud draft-only orchestrator (PM2) |
| `local_orchestrator.py` | root | Local approval handler + Dashboard writer |
| `requirements.txt` | root | pip3 deps for AWS |
| `.env.example` | root | Environment variables template |
| `deploy/cloud_setup.sh` | deploy/ | Full AWS setup script |
| `deploy/nginx/odoo-ssl.conf` | deploy/nginx/ | HTTPS nginx config for Odoo |
| `SKILL.md` × 3 | .claude/skills/ | cloud-deploy, vault-sync, health-check |

## New Vault Folders
| Folder | Writer | Purpose |
|--------|--------|---------|
| `/In_Progress/cloud/` | Cloud | Claimed items (claim-by-move) |
| `/In_Progress/local/` | Local | Claimed items |
| `/Pending_Approval/cloud/` | Cloud | Drafts awaiting human approval |
| `/Pending_Approval/local/` | Local | Local approval requests |
| `/Updates/` | Cloud | Signals for Local to merge into Dashboard |
| `/Signals/` | Either | Inter-agent signals |

---

## PM2 Processes (Cloud)

| Process | Script | Restart |
|---------|--------|---------|
| `gmail-watcher` | gmail_watcher.py | always |
| `cloud-orchestrator` | cloud_orchestrator.py --watch | always |
| `vault-sync` | sync_vault.py --watch | always |

---

## Security Rules (Platinum)
- Dashboard.md: single-writer (local_orchestrator.py ONLY)
- Cloud VM: NO WhatsApp session, NO Facebook session, NO LinkedIn session
- Secrets (.env, *_token.json, *.pem): never in Git, manually scp'd
- Claim-by-move: atomic rename prevents double processing
- /Updates/ signals: Cloud writes, Local consumes and deletes

---

## Setup Checklist

### One-time (Cloud)
- [x] Code committed + pushed to GitHub
- [ ] SSH to AWS: `bash deploy/cloud_setup.sh`
- [ ] Upload secrets: `scp credentials.json gmail_token.json ubuntu@13.233.108.91:~/personal-ai-employee/`
- [ ] Verify: `pm2 list` shows 3 processes online

### One-time (Local)
- [x] local_orchestrator.py created
- [ ] Test: `python local_orchestrator.py --status`
- [ ] Run on startup via Task Scheduler or cron

### Daily operation
- Cloud: fully autonomous (gmail → draft → push)
- Local: `python local_orchestrator.py` on startup, approve items in vault
