# Skill: vault-sync

Manage Git-based vault synchronisation between Cloud and Local agents.

## Trigger
Use when: "sync vault", "pull latest", "push changes", "vault out of sync"

## How Vault Sync Works (Platinum)

```
Cloud writes → git push → GitHub → git pull → Local reads
Local writes → git push → GitHub → git pull → Cloud reads
```

Sync runs automatically:
- **Cloud**: `sync_vault.py --watch` via PM2 (every 5 min)
- **Local**: `local_orchestrator.py` pulls on every cycle

## Manual Sync Commands

### Pull latest from cloud
```bash
python sync_vault.py --pull
```

### Full sync (pull + commit vault changes + push)
```bash
python sync_vault.py
```

### Check what would be synced
```bash
python sync_vault.py --status
```

### Force push with custom message
```bash
python sync_vault.py -m "manual: processed approvals"
```

## Security Rules
Only these vault paths are committed (secrets excluded):
- `AI_Employee_Vault/Needs_Action/`
- `AI_Employee_Vault/In_Progress/`
- `AI_Employee_Vault/Pending_Approval/`
- `AI_Employee_Vault/Updates/`
- `AI_Employee_Vault/Done/`
- `AI_Employee_Vault/Logs/`
- `AI_Employee_Vault/Plans/`
- `AI_Employee_Vault/Dashboard.md`

**Never synced** (in .gitignore):
- `*.json` token/session files
- `*_profile/` browser profiles
- `.env`, `credentials.json`

## Conflict Resolution
If git pull fails with conflicts:
```bash
git -C /mnt/c/Users/anzal/Desktop/AN-hack-0 status
# Resolve manually or:
git -C /mnt/c/Users/anzal/Desktop/AN-hack-0 checkout --ours AI_Employee_Vault/Dashboard.md
# (Local always wins Dashboard.md)
```

## Claim-by-Move Rule
To prevent double-processing:
1. Cloud moves item: `/Needs_Action/email.md` → `/In_Progress/cloud/email.md`
2. This rename is atomic — whoever does it first owns the item
3. Other agents see the file is gone from /Needs_Action and skip it
