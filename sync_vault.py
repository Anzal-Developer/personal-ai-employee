#!/usr/bin/env python3
"""
Vault Sync — AI Employee Platinum Tier
Git-based vault synchronisation between Cloud (AWS) and Local agents.

Security rule: ONLY markdown/state files are committed.
Secrets (.env, *_token.json, *_session.json, *_profile/) are excluded via .gitignore
and NEVER synced to Git.

Usage:
    python3 sync_vault.py           # pull + commit pending changes + push (once)
    python3 sync_vault.py --watch   # loop every SYNC_INTERVAL seconds (for PM2)
    python3 sync_vault.py --pull    # pull only
    python3 sync_vault.py --status  # show git status and exit

Environment variables (optional — set in systemd/PM2 env):
    REPO_DIR        /home/ubuntu/personal-ai-employee   (default: script parent)
    SYNC_INTERVAL   300                                 (seconds, default 300)
    AGENT_ID        cloud-vm-1                          (tag in commit messages)
    GIT_BRANCH      master                              (default: master)
"""

import argparse
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────

REPO_DIR = Path(os.getenv("REPO_DIR", Path(__file__).parent.resolve()))
VAULT_DIR = REPO_DIR / "AI_Employee_Vault"
LOGS_DIR = VAULT_DIR / "Logs"
SYNC_INTERVAL = int(os.getenv("SYNC_INTERVAL", "300"))
AGENT_ID = os.getenv("AGENT_ID", "cloud-vm-1")
GIT_BRANCH = os.getenv("GIT_BRANCH", "master")

# Vault subdirs safe to stage (never stage root for secrets safety)
SAFE_VAULT_PATHS = [
    "AI_Employee_Vault/Needs_Action/",
    "AI_Employee_Vault/In_Progress/",
    "AI_Employee_Vault/Pending_Approval/",
    "AI_Employee_Vault/Updates/",
    "AI_Employee_Vault/Signals/",
    "AI_Employee_Vault/Done/",
    "AI_Employee_Vault/Logs/",
    "AI_Employee_Vault/Plans/",
    "AI_Employee_Vault/Dashboard.md",
    "AI_Employee_Vault/Company_Handbook.md",
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def log(action: str, details: dict = None):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"{today}.jsonl"
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": AGENT_ID,
        "action": f"vault_sync:{action}",
        **(details or {}),
    }
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"[SYNC:{AGENT_ID}] {action}: {details or ''}")


def run_git(args: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Run a git command in REPO_DIR. Returns (returncode, stdout, stderr)."""
    result = subprocess.run(
        ["git", "-C", str(REPO_DIR)] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


# ── Sync Operations ────────────────────────────────────────────────────────────

def git_pull() -> bool:
    """Pull latest from remote (rebase to keep history clean)."""
    code, out, err = run_git(["pull", "--rebase", "origin", GIT_BRANCH])
    if code == 0:
        if "Already up to date" not in out:
            log("pull", {"result": out[:200]})
        return True
    else:
        log("pull_error", {"stderr": err[:300]})
        return False


def git_has_changes() -> bool:
    """Check if there are staged or unstaged changes in safe vault paths."""
    code, out, _ = run_git(["status", "--porcelain", "--"] + SAFE_VAULT_PATHS)
    return bool(out.strip())


def git_commit_and_push(message: str = None) -> bool:
    """Stage safe vault paths, commit, and push."""
    # Stage only vault state files
    stage_args = ["add"] + SAFE_VAULT_PATHS
    run_git(stage_args)

    if not git_has_staged_changes():
        return True  # nothing to commit, that's fine

    commit_msg = message or f"[{AGENT_ID}] vault-sync {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M')}"
    code, out, err = run_git(["commit", "-m", commit_msg])
    if code != 0 and "nothing to commit" not in out:
        log("commit_error", {"stderr": err[:200]})
        return False

    # Push
    code, out, err = run_git(["push", "origin", GIT_BRANCH], timeout=60)
    if code == 0:
        log("push", {"message": commit_msg})
        return True
    else:
        log("push_error", {"stderr": err[:300]})
        return False


def git_has_staged_changes() -> bool:
    code, out, _ = run_git(["diff", "--cached", "--quiet"])
    return code != 0  # non-zero = has staged changes


def git_status() -> str:
    _, out, _ = run_git(["status", "--short"])
    return out


# ── Secrets Safety Check ───────────────────────────────────────────────────────

FORBIDDEN_PATTERNS = [
    "gmail_token.json",
    "gmail_send_token.json",
    "credentials.json",
    "linkedin_session.json",
    "facebook_session.json",
    "facebook_seen.json",
    ".env",
    "*.pem",
    "*.key",
]


def check_no_secrets_staged() -> bool:
    """Abort if any secret file is about to be committed."""
    _, out, _ = run_git(["diff", "--cached", "--name-only"])
    staged = out.splitlines()
    for filepath in staged:
        for pattern in FORBIDDEN_PATTERNS:
            name = Path(filepath).name
            if pattern.startswith("*"):
                if name.endswith(pattern[1:]):
                    print(f"[SYNC] SECURITY: Refusing to commit secret file: {filepath}")
                    log("security_abort", {"file": filepath, "pattern": pattern})
                    run_git(["reset", "HEAD", "--", filepath])
                    return False
            else:
                if name == pattern:
                    print(f"[SYNC] SECURITY: Refusing to commit secret file: {filepath}")
                    log("security_abort", {"file": filepath})
                    run_git(["reset", "HEAD", "--", filepath])
                    return False
    return True


# ── Main Sync Cycle ────────────────────────────────────────────────────────────

def sync_once(message: str = None) -> bool:
    """Full sync cycle: commit local changes → pull → push.
    Order matters: commit first so 'git pull --rebase' never fails on dirty tree.
    """
    ok = True

    # 1. Stage + commit any local vault changes FIRST (so pull is clean)
    if git_has_changes():
        check_no_secrets_staged()   # strip any accidental secrets
        git_commit_and_push(message)

    # 2. Pull latest from remote (now safe — working tree is clean)
    if not git_pull():
        ok = False

    # 3. If the pull brought new changes that need a second push (rare), do it
    run_git(["add"] + SAFE_VAULT_PATHS)
    if git_has_staged_changes():
        check_no_secrets_staged()
        git_commit_and_push(f"[{AGENT_ID}] post-pull sync")

    return ok


# ── Entry Point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Vault Sync — Platinum Tier")
    parser.add_argument("--watch", action="store_true", help=f"Sync every {SYNC_INTERVAL}s (PM2 mode)")
    parser.add_argument("--pull", action="store_true", help="Pull only")
    parser.add_argument("--status", action="store_true", help="Show git status and exit")
    parser.add_argument("--message", "-m", default=None, help="Custom commit message")
    args = parser.parse_args()

    if args.status:
        print(git_status() or "Nothing to sync.")
        return

    if args.pull:
        git_pull()
        return

    print("=" * 55)
    print(f"  Vault Sync — {AGENT_ID}")
    print(f"  Repo:  {REPO_DIR}")
    print(f"  Mode:  {'watch' if args.watch else 'once'}")
    print("=" * 55)

    if not args.watch:
        sync_once(args.message)
        return

    print(f"  Syncing every {SYNC_INTERVAL}s. Ctrl+C to stop.\n")
    try:
        while True:
            sync_once()
            time.sleep(SYNC_INTERVAL)
    except KeyboardInterrupt:
        print("\n[SYNC] Stopped.")


if __name__ == "__main__":
    main()
