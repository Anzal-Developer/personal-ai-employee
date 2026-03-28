# Skill: cloud-deploy

Deploy or update the AI Employee cloud agent on the AWS VM.

## Trigger
Use when user says: "deploy to cloud", "update AWS", "redeploy", "setup cloud agent"

## Architecture (Platinum)

```
Cloud VM (AWS 13.233.108.91)        Git (GitHub)         Local PC
────────────────────────────        ────────────         ────────
gmail_watcher.py (24/7)    ──push──▶ master ◀──pull── local_orchestrator.py
cloud_orchestrator.py (PM2)                              (approvals, send/post)
sync_vault.py (PM2, 5 min)                               Dashboard.md (single writer)
```

## Deploy Steps

### 1. Push latest code
```bash
git add -A && git commit -m "deploy: update" && git push origin master
```

### 2. SSH to AWS and redeploy
```bash
ssh -i "/mnt/c/Users/anzal/Downloads/hackathon.pem" ubuntu@13.233.108.91 \
  "cd /home/ubuntu/personal-ai-employee && \
   git pull && \
   pip3 install -r requirements.txt && \
   pm2 restart vault-sync && \
   pm2 restart cloud-orchestrator && \
   pm2 restart gmail-watcher 2>/dev/null || true && \
   pm2 save"
```

### 3. Full fresh setup (first time)
```bash
ssh -i "/mnt/c/Users/anzal/Downloads/hackathon.pem" ubuntu@13.233.108.91 \
  "cd /home/ubuntu/personal-ai-employee && bash deploy/cloud_setup.sh"
```

### 4. Upload secrets (after setup — ONE TIME, never via Git)
```bash
# From WSL/terminal:
scp -i "/mnt/c/Users/anzal/Downloads/hackathon.pem" \
    credentials.json gmail_token.json \
    ubuntu@13.233.108.91:/home/ubuntu/personal-ai-employee/
```

## Monitor Cloud

```bash
# PM2 status
ssh -i "/mnt/c/Users/anzal/Downloads/hackathon.pem" ubuntu@13.233.108.91 "pm2 list"

# Logs
ssh -i "/mnt/c/Users/anzal/Downloads/hackathon.pem" ubuntu@13.233.108.91 "pm2 logs --lines 50"

# Health check
ssh -i "/mnt/c/Users/anzal/Downloads/hackathon.pem" ubuntu@13.233.108.91 \
    "cd /home/ubuntu/personal-ai-employee && python3 cloud_orchestrator.py --health"
```

## Security Rules (Platinum)
- NEVER commit .env, *_token.json, credentials.json, *_session.json to Git
- Cloud VM never stores WhatsApp session, Facebook session, or LinkedIn session
- Cloud only drafts — Local executes all final send/post actions
- Dashboard.md is written ONLY by local_orchestrator.py
