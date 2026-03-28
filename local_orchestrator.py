#!/usr/bin/env python3
"""
Local Orchestrator — AI Employee Platinum Tier
Runs on your local PC. Owns: approvals, send/post, Dashboard.md, WhatsApp, payments.

Platinum flow this handles:
  1. Pull latest vault from Git (gets Cloud's drafts)
  2. Scan /Pending_Approval/cloud/ — show what Cloud drafted
  3. Human moves file to /Approved/ → Local executes action
  4. Scan /Approved/ and dispatch:
       - DRAFT_REPLY_*.md  → gmail_sender.py
       - DRAFT_POST_FACEBOOK_*.md → facebook_poster.py --once
       - DRAFT_POST_LINKEDIN_*.md → linkedin_poster.py  --once
  5. Merge /Updates/SIGNAL_*.md into Dashboard.md
  6. Push vault back to Git

Usage:
    python local_orchestrator.py              # full cycle once (on startup)
    python local_orchestrator.py --watch      # loop every 60s
    python local_orchestrator.py --send-approved  # process /Approved only
    python local_orchestrator.py --dashboard  # rebuild Dashboard.md and exit
    python local_orchestrator.py --status     # show pending items and exit

Security: This machine owns secrets (tokens, sessions).
          Dashboard.md is the SINGLE-WRITER file — only Local writes it.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────

BASE_DIR   = Path(__file__).parent.resolve()
VAULT_DIR  = BASE_DIR / "AI_Employee_Vault"
AGENT_ID   = os.getenv("AGENT_ID", "local-pc")
WATCH_INTERVAL = int(os.getenv("WATCH_INTERVAL", "60"))

PENDING_CLOUD  = VAULT_DIR / "Pending_Approval" / "cloud"
PENDING_LOCAL  = VAULT_DIR / "Pending_Approval" / "local"
APPROVED       = VAULT_DIR / "Approved"
REJECTED       = VAULT_DIR / "Rejected"
DONE           = VAULT_DIR / "Done"
UPDATES        = VAULT_DIR / "Updates"
LOGS           = VAULT_DIR / "Logs"
DASHBOARD      = VAULT_DIR / "Dashboard.md"
IN_PROG_LOCAL  = VAULT_DIR / "In_Progress" / "local"


# ── Logging ────────────────────────────────────────────────────────────────────

def log(action: str, details: dict = None):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = LOGS / f"{today}.jsonl"
    LOGS.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": AGENT_ID,
        "action": action,
        **(details or {}),
    }
    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"[{AGENT_ID}] {action}: {details or ''}")


# ── Git helpers ────────────────────────────────────────────────────────────────

def git(args: list[str], timeout: int = 30) -> tuple[int, str]:
    r = subprocess.run(["git", "-C", str(BASE_DIR)] + args,
                       capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout.strip()


def vault_pull():
    code, out = git(["pull", "--rebase", "origin", "master"])
    if code == 0:
        log("git_pull", {"result": out[:100] if out else "up-to-date"})
    else:
        log("git_pull_error", {"output": out[:200]})


def vault_push(message: str = None):
    safe = [
        "AI_Employee_Vault/Done/",
        "AI_Employee_Vault/Logs/",
        "AI_Employee_Vault/Dashboard.md",
        "AI_Employee_Vault/Pending_Approval/",
        "AI_Employee_Vault/Approved/",
        "AI_Employee_Vault/Rejected/",
        "AI_Employee_Vault/Updates/",
        "AI_Employee_Vault/In_Progress/",
    ]
    git(["add"] + safe)
    msg = message or f"[{AGENT_ID}] local-sync {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M')}"
    code, out = git(["commit", "-m", msg])
    if "nothing to commit" in out:
        return
    git(["push", "origin", "master"], timeout=60)
    log("git_push", {"message": msg})


# ── Dispatch approved files ───────────────────────────────────────────────────

def read_frontmatter(path: Path) -> dict:
    meta = {}
    try:
        parts = path.read_text(encoding="utf-8", errors="replace").split("---")
        if len(parts) >= 3:
            for line in parts[1].splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    meta[k.strip()] = v.strip()
    except Exception:
        pass
    return meta


def run_script(cmd: list[str]) -> bool:
    """Run a local script (gmail_sender, linkedin_poster, etc.)."""
    print(f"[{AGENT_ID}] Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            [sys.executable] + cmd,
            cwd=str(BASE_DIR),
            timeout=120,
        )
        return result.returncode == 0
    except Exception as e:
        print(f"[{AGENT_ID}] Script error: {e}")
        return False


def archive_approved(filepath: Path, label: str):
    DONE.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest = DONE / f"DONE_{ts}_{AGENT_ID}_{filepath.name}"
    filepath.rename(dest)
    log("approved_archived", {"from": filepath.name, "to": dest.name, "label": label})


def process_approved_file(filepath: Path) -> bool:
    """Dispatch an approved file to the correct executor."""
    meta  = read_frontmatter(filepath)
    atype = meta.get("type", "")
    name  = filepath.name.upper()

    # ── Draft email reply → gmail_sender.py ──────────────────────────────────
    if atype == "draft_email_reply" or name.startswith("DRAFT_REPLY_"):
        to      = meta.get("to", meta.get("from", ""))
        subject = meta.get("subject", "(no subject)")
        # Extract reply body
        content = filepath.read_text(encoding="utf-8", errors="replace")
        parts = content.split("## Draft Reply")
        body = parts[1].strip() if len(parts) > 1 else "(no body)"
        # Strip the "## How to Approve" section
        body = body.split("---\n\n## How to Approve")[0].strip()
        body = body.lstrip("*(Review, edit if needed, then move this file to `/Approved/` to send)*").strip()

        if not to:
            log("send_skip", {"reason": "no recipient", "file": filepath.name})
            return False

        ok = run_script([
            "gmail_sender.py",
            "--to", to,
            "--subject", f"Re: {subject}",
            "--body", body,
        ])
        if ok:
            archive_approved(filepath, "email_sent")
            log("email_sent", {"to": to, "subject": subject})
        return ok

    # ── Draft LinkedIn post → linkedin_poster.py ─────────────────────────────
    elif atype == "draft_social_post" and "linkedin" in name.lower():
        # Rename to linkedin_poster expected pattern then call --once
        ln_file = APPROVED / filepath.name.replace("DRAFT_POST_", "LINKEDIN_POST_")
        filepath.rename(ln_file)
        ok = run_script(["linkedin_poster.py", "--once"])
        if ok:
            log("linkedin_post_dispatched", {"file": ln_file.name})
        return ok

    # ── Draft Facebook post → facebook_poster.py ─────────────────────────────
    elif atype == "draft_social_post" and "facebook" in name.lower():
        fb_file = APPROVED / filepath.name.replace("DRAFT_POST_", "FACEBOOK_POST_")
        filepath.rename(fb_file)
        ok = run_script(["facebook_poster.py", "--once"])
        if ok:
            log("facebook_post_dispatched", {"file": fb_file.name})
        return ok

    # ── Legacy LINKEDIN_POST_*.md ─────────────────────────────────────────────
    elif name.startswith("LINKEDIN_POST_"):
        ok = run_script(["linkedin_poster.py", "--once"])
        return ok

    # ── Legacy FACEBOOK_POST_*.md ─────────────────────────────────────────────
    elif name.startswith("FACEBOOK_POST_"):
        ok = run_script(["facebook_poster.py", "--once"])
        return ok

    else:
        log("approved_unknown_type", {"file": filepath.name, "type": atype})
        return False


def process_all_approved():
    """Process everything in /Approved/."""
    if not APPROVED.exists():
        return 0
    files = [f for f in APPROVED.iterdir() if f.is_file() and f.suffix == ".md"]
    count = 0
    for f in files:
        success = process_approved_file(f)
        if success:
            count += 1
    return count


# ── Pending summary ────────────────────────────────────────────────────────────

def pending_items() -> list[dict]:
    """Return all items in /Pending_Approval/cloud/ awaiting human review."""
    items = []
    if PENDING_CLOUD.exists():
        for f in sorted(PENDING_CLOUD.glob("*.md")):
            meta = read_frontmatter(f)
            age_s = (datetime.now(timezone.utc).timestamp() -
                     f.stat().st_mtime)
            items.append({
                "file": f.name,
                "type": meta.get("type", "unknown"),
                "subject": meta.get("subject", ""),
                "from": meta.get("from", ""),
                "age_hours": round(age_s / 3600, 1),
                "path": str(f),
            })
    return items


def print_pending_summary():
    items = pending_items()
    if not items:
        print(f"[{AGENT_ID}] No items pending in /Pending_Approval/cloud/")
        return
    print(f"\n[{AGENT_ID}] {len(items)} item(s) awaiting your approval:\n")
    for i, item in enumerate(items, 1):
        print(f"  {i}. [{item['type']}] {item.get('subject') or item['file']}")
        if item.get("from"):
            print(f"     From: {item['from']}")
        print(f"     Age:  {item['age_hours']}h   →  {item['path']}")
    print(f"\n  To approve: move file to AI_Employee_Vault/Approved/")
    print(f"  To reject:  move file to AI_Employee_Vault/Rejected/\n")


# ── Signal merge into Dashboard ────────────────────────────────────────────────

def merge_signals_into_dashboard():
    """
    Consume /Updates/SIGNAL_*.md files and append a summary to Dashboard.md.
    Local is the SINGLE WRITER of Dashboard.md.
    """
    if not UPDATES.exists():
        return

    signals = sorted(UPDATES.glob("SIGNAL_*.md"))
    if not signals:
        return

    new_entries = []
    for sig in signals:
        try:
            content = sig.read_text(encoding="utf-8", errors="replace")
            new_entries.append(f"- {sig.name}: {content[:150].replace(chr(10),' ')}")
            sig.unlink()
        except Exception as e:
            log("signal_read_error", {"file": sig.name, "error": str(e)})

    if not new_entries:
        return

    # Append to Dashboard.md
    DASHBOARD.parent.mkdir(parents=True, exist_ok=True)
    existing = DASHBOARD.read_text(encoding="utf-8") if DASHBOARD.exists() else "# Dashboard\n"
    ts_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    section = f"\n## Cloud Updates merged {ts_now}\n" + "\n".join(new_entries) + "\n"
    DASHBOARD.write_text(existing + section, encoding="utf-8")
    log("dashboard_updated", {"signals_merged": len(new_entries)})


def rebuild_dashboard():
    """Write a fresh Dashboard.md with current vault state."""
    needs_count   = len([f for f in (VAULT_DIR / "Needs_Action").rglob("*.md")
                         if not f.name.startswith(".")])
    pending_count = len(list(PENDING_CLOUD.glob("*.md"))) if PENDING_CLOUD.exists() else 0
    approved_count = len(list(APPROVED.glob("*.md"))) if APPROVED.exists() else 0
    done_today    = len([f for f in DONE.glob("*.md")
                         if datetime.fromtimestamp(f.stat().st_mtime).date()
                         == datetime.now().date()]) if DONE.exists() else 0

    pending_items_list = pending_items()

    content = f"""# AI Employee Dashboard
*Last updated by Local Agent ({AGENT_ID}) — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*

---

## Queue Status
| Folder | Count |
|--------|-------|
| /Needs_Action | {needs_count} |
| /Pending_Approval/cloud (awaiting you) | {pending_count} |
| /Approved (queued for execution) | {approved_count} |
| /Done (completed today) | {done_today} |

---

## Pending Approvals (Cloud Drafts)
"""
    if pending_items_list:
        for item in pending_items_list:
            content += f"- **{item.get('subject') or item['file']}** ({item['age_hours']}h old)\n"
            content += f"  `{item['path']}`\n"
    else:
        content += "*No pending approvals — all clear!*\n"

    content += f"""
---

## Architecture
```
Cloud (AWS 24/7)              Git Sync             Local (Your PC)
────────────────              ────────             ────────────────
gmail_watcher.py  ──writes──▶ /Needs_Action    ◀──pulls── local_orchestrator.py
cloud_orchestrator.py ──▶ /Pending_Approval/cloud  ──▶  (you approve) ──▶ gmail_sender.py
sync_vault.py (every 5 min)                         local_orchestrator.py ──▶ Dashboard.md
```

---
*Single-writer rule: Only `local_orchestrator.py` writes this file.*
"""
    DASHBOARD.write_text(content, encoding="utf-8")
    log("dashboard_rebuilt", {"pending": pending_count, "needs": needs_count})


# ── Main cycle ─────────────────────────────────────────────────────────────────

def run_cycle():
    vault_pull()
    merge_signals_into_dashboard()
    process_all_approved()
    rebuild_dashboard()
    print_pending_summary()
    vault_push()


def main():
    parser = argparse.ArgumentParser(description="Local Orchestrator — Platinum Tier")
    parser.add_argument("--watch",         action="store_true", help=f"Loop every {WATCH_INTERVAL}s")
    parser.add_argument("--send-approved", action="store_true", help="Process /Approved only")
    parser.add_argument("--dashboard",     action="store_true", help="Rebuild Dashboard.md and push")
    parser.add_argument("--status",        action="store_true", help="Show pending items and exit")
    args = parser.parse_args()

    if args.status:
        vault_pull()
        print_pending_summary()
        return

    if args.dashboard:
        rebuild_dashboard()
        vault_push("local: dashboard rebuild")
        return

    if args.send_approved:
        n = process_all_approved()
        vault_push(f"local: executed {n} approved action(s)")
        return

    print("=" * 58)
    print(f"  Local Orchestrator — {AGENT_ID}")
    print(f"  Vault : {VAULT_DIR}")
    print(f"  Mode  : {'watch' if args.watch else 'once'}")
    print("=" * 58)

    log("local_orchestrator_started", {"mode": "watch" if args.watch else "once"})

    if not args.watch:
        run_cycle()
        return

    print(f"  Checking every {WATCH_INTERVAL}s. Ctrl+C to stop.\n")
    try:
        while True:
            run_cycle()
            time.sleep(WATCH_INTERVAL)
    except KeyboardInterrupt:
        log("local_orchestrator_stopped", {"reason": "keyboard_interrupt"})
        print(f"\n[{AGENT_ID}] Stopped.")


if __name__ == "__main__":
    main()
