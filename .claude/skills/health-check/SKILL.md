# Skill: health-check

Check the health of all AI Employee components — local and cloud.

## Trigger
Use when: "health check", "is everything running?", "check cloud", "system status"

## What to Check

### 1. Cloud VM (AWS)
```bash
ssh -i "/mnt/c/Users/anzal/Downloads/hackathon.pem" ubuntu@13.233.108.91 \
  "pm2 list && python3 /home/ubuntu/personal-ai-employee/cloud_orchestrator.py --health"
```

Expected: 3 PM2 processes online (gmail-watcher, cloud-orchestrator, vault-sync)

### 2. Local processes
```bash
python local_orchestrator.py --status
```
Shows: pending approvals from cloud, items in /Needs_Action

### 3. Vault sync status
```bash
python sync_vault.py --status
git log --oneline -5
```

### 4. Odoo (Gold Tier)
```bash
docker compose ps
curl -s http://localhost:8069/web/health | head -5
```

### 5. GitHub repo (latest push)
```bash
git log --oneline -3 origin/master
```

## Health Report Format

Generate a health report and save to `AI_Employee_Vault/Updates/HEALTH_YYYY-MM-DD.md`:

```markdown
# System Health — YYYY-MM-DD HH:MM UTC

## Cloud (AWS 13.233.108.91)
- [ ] gmail-watcher: online/offline
- [ ] cloud-orchestrator: online/offline
- [ ] vault-sync: online/offline
- Last sync: <timestamp>

## Local
- Pending approvals: N items
- Needs action: N items
- Approved (queued): N items

## Odoo
- Status: running/stopped
- URL: http://localhost:8069

## Vault
- Last git pull: <timestamp>
- Last git push: <timestamp>
- Unsynced changes: yes/no

## Alerts
<any issues found>
```

## Common Issues & Fixes

| Issue | Fix |
|-------|-----|
| PM2 process offline | `ssh ubuntu@13.233.108.91 "pm2 restart all"` |
| Vault out of sync | `python sync_vault.py` |
| Gmail token expired | Re-run `python gmail_auth.py` locally, scp token to cloud |
| Odoo not responding | `docker compose restart odoo` |
| Git push fails | Check SSH key / HTTPS token: `git remote -v` |
