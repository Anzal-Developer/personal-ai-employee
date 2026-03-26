# Gold Tier Implementation Plan
**Created:** 2026-03-26
**Status:** COMPLETE ✓

---

## Objective
Complete the Gold Tier hackathon deliverables:
- [x] Facebook integration (watcher + poster + skill)
- [x] Odoo Community accounting (Docker Compose + MCP server + skill)
- [x] Ralph Wiggum autonomous loop (stop hook)
- [x] CEO Briefing skill
- [x] Multiple MCP servers (odoo)
- [x] Comprehensive audit logging
- [x] Error recovery and graceful degradation
- [x] All AI functionality as Agent Skills

---

## Architecture

```
Watchers (Perception)          Claude Code (Reasoning)        Actions (Hands)
─────────────────────          ───────────────────────        ───────────────
gmail_watcher.py      ──┐
linkedin_watcher.py   ──┼──→  /Needs_Action/*.md  ──→  Skills + MCP Tools
facebook_watcher.py   ──┘
watcher.py (files)    ────→  /Inbox/*.md                      │
                                                              ┌▼──────────────────┐
                              Ralph Wiggum Stop Hook ────────→│ Autonomous Loop   │
                              (re-inject prompt if             │ max 10 iterations  │
                               items remain)                   └───────────────────┘

MCP Servers:
  odoo  ──→  http://localhost:8069 (Docker)
              XML-RPC: invoices, customers, expenses, financial summary

HITL Workflow:
  Draft ──→ /Pending_Approval/ ──→ [Human] ──→ /Approved/ ──→ Action ──→ /Done/
```

---

## Files Created

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Odoo 17 + PostgreSQL 16 |
| `odoo.conf` | Odoo server config |
| `odoo_mcp.py` | MCP server (FastMCP + XML-RPC) |
| `facebook_poster.py` | Playwright HITL Facebook poster |
| `facebook_watcher.py` | Facebook notification watcher |
| `ralph_wiggum.sh` | Stop hook for autonomous loop |
| `.claude/settings.json` | MCP servers + Stop hook config |
| `.claude/skills/facebook-post/` | Facebook post skill |
| `.claude/skills/odoo-accounting/` | Odoo accounting skill |
| `.claude/skills/ceo-briefing/` | Weekly CEO briefing skill |

---

## Setup Instructions

### 1. Start Odoo
```bash
docker compose up -d
# Wait ~60 seconds for first boot
# Visit http://localhost:8069
# Create database "odoo", set admin password to "admin"
# Install: Accounting, Contacts, Sales, Purchase modules
```

### 2. Setup Facebook session (one-time)
```bash
uv run facebook_poster.py --setup
# OR
uv run facebook_watcher.py --setup
```

### 3. Start all watchers
```bash
# In separate terminals:
uv run gmail_watcher.py
uv run linkedin_watcher.py
uv run facebook_watcher.py
uv run linkedin_poster.py
uv run facebook_poster.py
```

### 4. Test Odoo MCP
In Claude Code: "check odoo connection" → triggers `check_odoo_connection` tool

### 5. Generate CEO Briefing
In Claude Code: `/ceo-briefing`

---

## Gold Tier Checklist (from Hackathon Doc)

- [x] All Silver requirements
- [x] Full cross-domain integration (Personal + Business)
- [x] Odoo Community self-hosted + MCP integration
- [x] Facebook integration (post + monitor)
- [ ] Twitter/X integration (not built — out of scope per user)
- [x] Multiple MCP servers (odoo configured)
- [x] Weekly Business and Accounting Audit (CEO Briefing skill)
- [x] Error recovery and graceful degradation (try/except + screenshots)
- [x] Comprehensive audit logging (JSONL per day)
- [x] Ralph Wiggum loop (Stop hook + iteration limiter)
- [x] Documentation (this plan + updated Company_Handbook.md)
- [x] All AI functionality as Agent Skills
