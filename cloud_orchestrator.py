#!/usr/bin/env python3
"""
Cloud Orchestrator — AI Employee Platinum Tier
Runs 24/7 on AWS. DRAFT-ONLY zone — no secrets, no send, no post.

Work-zone rules (Platinum spec):
  Cloud OWNS:  Email triage, draft replies, social post drafts
  Cloud NEVER: Sends email, posts to social, confirms invoices, touches WhatsApp

Flow (Platinum demo gate):
  1. gmail_watcher.py writes GMAIL_*.md → /Needs_Action/
  2. cloud_orchestrator.py claims it  → /In_Progress/cloud/
  3. Drafts reply                     → /Pending_Approval/cloud/DRAFT_REPLY_*.md
  4. Writes signal                    → /Updates/SIGNAL_*.md
  5. Marks item done                  → /Done/
  6. sync_vault.py pushes to Git
  7. Local pulls, sees /Pending_Approval/cloud/ items
  8. Human approves → Local sends via gmail_sender.py

Claim-by-move rule: atomic rename to /In_Progress/cloud/ — whoever wins owns it.

Usage:
    python3 cloud_orchestrator.py           # run once (cron)
    python3 cloud_orchestrator.py --watch   # loop every 2 min (PM2)
    python3 cloud_orchestrator.py --health  # print health status

Environment:
    REPO_DIR        /home/ubuntu/personal-ai-employee
    AGENT_ID        cloud-vm-1
    MAX_CLAIMS      10
"""

import argparse
import json
import os
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────

REPO_DIR    = Path(os.getenv("REPO_DIR", Path(__file__).parent.resolve()))
VAULT_DIR   = REPO_DIR / "AI_Employee_Vault"
AGENT_ID    = os.getenv("AGENT_ID", "cloud-vm-1")
MAX_CLAIMS  = int(os.getenv("MAX_CLAIMS", "10"))
WATCH_INTERVAL = 120  # seconds

NEEDS_ACTION      = VAULT_DIR / "Needs_Action"
IN_PROGRESS_CLOUD = VAULT_DIR / "In_Progress" / "cloud"
PENDING_CLOUD     = VAULT_DIR / "Pending_Approval" / "cloud"
UPDATES           = VAULT_DIR / "Updates"
DONE              = VAULT_DIR / "Done"
LOGS              = VAULT_DIR / "Logs"


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


# ── Vault helpers ──────────────────────────────────────────────────────────────

def read_content(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def read_frontmatter(path: Path) -> dict:
    meta = {}
    try:
        parts = read_content(path).split("---")
        if len(parts) >= 3:
            for line in parts[1].splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    meta[k.strip()] = v.strip()
    except Exception:
        pass
    return meta


def slug(text: str, maxlen: int = 40) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower())[:maxlen].strip("_")


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


# ── Claim-by-Move ─────────────────────────────────────────────────────────────

def claim(filepath: Path) -> Path | None:
    """
    Atomic move from /Needs_Action → /In_Progress/cloud/.
    Returns new path on success, None if already claimed.
    """
    IN_PROGRESS_CLOUD.mkdir(parents=True, exist_ok=True)
    dest = IN_PROGRESS_CLOUD / filepath.name
    try:
        filepath.rename(dest)
        log("claimed", {"file": filepath.name})
        return dest
    except FileNotFoundError:
        return None  # Another agent won the race
    except Exception as e:
        log("claim_error", {"file": filepath.name, "error": str(e)})
        return None


def release(filepath: Path, reason: str):
    """Return item to /Needs_Action if processing fails."""
    try:
        filepath.rename(NEEDS_ACTION / filepath.name)
        log("released", {"file": filepath.name, "reason": reason})
    except Exception as e:
        log("release_error", {"file": filepath.name, "error": str(e)})


def archive(filepath: Path, label: str):
    """Move processed item to /Done/."""
    DONE.mkdir(parents=True, exist_ok=True)
    dest = DONE / f"DONE_{ts()}_{AGENT_ID}_{filepath.name}"
    shutil.copy2(filepath, dest)
    filepath.unlink(missing_ok=True)
    log("archived", {"from": filepath.name, "to": dest.name, "label": label})


# ── Signal writer ──────────────────────────────────────────────────────────────

def write_signal(kind: str, payload: dict):
    """Write a /Updates/SIGNAL_*.md for Local agent to merge into Dashboard."""
    UPDATES.mkdir(parents=True, exist_ok=True)
    sig = UPDATES / f"SIGNAL_{kind.upper()}_{ts()}.md"
    sig.write_text(
        f"""---
type: signal
signal: {kind}
from: {AGENT_ID}
timestamp: {datetime.now(timezone.utc).isoformat()}
---

```json
{json.dumps(payload, indent=2)}
```
""",
        encoding="utf-8",
    )


# ── Draft builders ─────────────────────────────────────────────────────────────

def build_email_draft(claimed: Path, meta: dict, body: str) -> Path:
    """
    Create /Pending_Approval/cloud/DRAFT_REPLY_*.md.
    Local agent will review this and, on approval, send via gmail_sender.py.
    """
    PENDING_CLOUD.mkdir(parents=True, exist_ok=True)
    sender   = meta.get("from", "unknown")
    subject  = meta.get("subject", "(no subject)")
    out_name = f"DRAFT_REPLY_{ts()}_{slug(subject)}.md"
    out      = PENDING_CLOUD / out_name

    # Extract the email snippet for context
    snippet = ""
    parts = body.split("---")
    if len(parts) >= 3:
        snippet = "---".join(parts[2:]).strip()[:600]

    out.write_text(
        f"""---
type: draft_email_reply
status: pending_local_approval
action_required: send_email
source_item: {claimed.name}
from: {sender}
subject: {subject}
to: {sender}
created_by: {AGENT_ID}
created_at: {datetime.now(timezone.utc).isoformat()}
---

## Original Message
**From:** {sender}
**Subject:** {subject}

{snippet}

---

## Draft Reply
*(Review, edit if needed, then move this file to `/Approved/` to send)*

Hi,

Thank you for your email regarding "{subject}". I've received your message
and will review it carefully.

I'll follow up with a detailed response within 24 hours.

Best regards,
Anzal

---

## How to Approve
1. Edit the reply above if needed
2. Move this file to `AI_Employee_Vault/Approved/`
3. Run: `python local_orchestrator.py --send-approved`

## How to Reject
Move this file to `AI_Employee_Vault/Rejected/`
""",
        encoding="utf-8",
    )
    log("draft_created", {"draft": out_name, "from": sender, "subject": subject})
    return out


def build_social_draft(claimed: Path, meta: dict, body: str, platform: str) -> Path:
    """Create a draft social post for Local to review and post."""
    PENDING_CLOUD.mkdir(parents=True, exist_ok=True)
    out_name = f"DRAFT_POST_{platform.upper()}_{ts()}.md"
    out = PENDING_CLOUD / out_name
    snippet = body[:300]

    out.write_text(
        f"""---
type: draft_social_post
platform: {platform}
status: pending_local_approval
action_required: post_{platform}
source_item: {claimed.name}
created_by: {AGENT_ID}
created_at: {datetime.now(timezone.utc).isoformat()}
---

## Source Notification
{snippet}

---

## Proposed {platform.title()} Post

---
Interesting update from the AI employee! Here's what's happening:

{snippet[:200]}

Stay tuned for more updates. 🤖

#AI #Automation #BuildInPublic
---

## How to Approve
Move this file to `AI_Employee_Vault/Approved/` to publish via
`{platform}_poster.py --once`
""",
        encoding="utf-8",
    )
    log("social_draft_created", {"draft": out_name, "platform": platform})
    return out


# ── Item dispatcher ────────────────────────────────────────────────────────────

def detect_type(filename: str) -> str:
    n = filename.upper()
    if n.startswith("GMAIL_"):
        return "email"
    if n.startswith("LINKEDIN_"):
        return "linkedin"
    if n.startswith("FACEBOOK_"):
        return "facebook"
    if n.startswith("DROP_"):
        return "file_drop"
    return "unknown"


def process(claimed: Path):
    meta    = read_frontmatter(claimed)
    body    = read_content(claimed)
    kind    = detect_type(claimed.name)

    if kind == "email":
        draft = build_email_draft(claimed, meta, body)
        write_signal("approval_needed", {
            "type": "email_reply",
            "draft": draft.name,
            "from": meta.get("from", "?"),
            "subject": meta.get("subject", "?"),
            "message": "Cloud drafted a reply. Local: pull vault and check /Pending_Approval/cloud/",
        })
        archive(claimed, "email_drafted")

    elif kind in ("linkedin", "facebook"):
        draft = build_social_draft(claimed, meta, body, kind)
        write_signal("approval_needed", {
            "type": "social_draft",
            "platform": kind,
            "draft": draft.name,
        })
        archive(claimed, f"{kind}_draft_created")

    elif kind == "file_drop":
        # Escalate to Local for human decision
        PENDING_CLOUD.mkdir(parents=True, exist_ok=True)
        review = PENDING_CLOUD / f"REVIEW_DROP_{ts()}_{slug(claimed.stem)}.md"
        review.write_text(
            f"""---
type: file_drop_review
source_item: {claimed.name}
created_by: {AGENT_ID}
created_at: {datetime.now(timezone.utc).isoformat()}
status: pending_local_review
---

## File Drop Requires Human Decision

{body[:800]}

---
Move to `/Approved/` with a note, or `/Rejected/` to discard.
""",
            encoding="utf-8",
        )
        write_signal("review_needed", {"type": "file_drop", "file": claimed.name})
        archive(claimed, "escalated_to_local")

    else:
        log("unknown_type", {"file": claimed.name})
        release(claimed, "unknown_type")


# ── Main ───────────────────────────────────────────────────────────────────────

def run_once() -> int:
    items = sorted(
        [f for f in NEEDS_ACTION.iterdir()
         if f.is_file() and f.suffix == ".md" and not f.name.startswith(".")],
        key=lambda f: f.stat().st_mtime,
    )

    if not items:
        print(f"[{AGENT_ID}] /Needs_Action is empty.")
        return 0

    processed = 0
    for item in items[:MAX_CLAIMS]:
        claimed = claim(item)
        if not claimed:
            continue
        try:
            process(claimed)
            processed += 1
        except Exception as e:
            log("process_error", {"file": item.name, "error": str(e)})
            release(claimed, f"error: {e}")

    log("run_complete", {"processed": processed, "total_found": len(items)})
    return processed


def health() -> dict:
    pending = len(list(PENDING_CLOUD.glob("*.md"))) if PENDING_CLOUD.exists() else 0
    needs   = len([f for f in NEEDS_ACTION.glob("*.md")
                   if not f.name.startswith(".")]) if NEEDS_ACTION.exists() else 0
    in_prog = len(list(IN_PROGRESS_CLOUD.glob("*.md"))) if IN_PROGRESS_CLOUD.exists() else 0
    return {
        "agent": AGENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "needs_action": needs,
        "in_progress_cloud": in_prog,
        "pending_approval_cloud": pending,
        "status": "healthy",
    }


def main():
    parser = argparse.ArgumentParser(description="Cloud Orchestrator — Platinum Tier")
    parser.add_argument("--watch",  action="store_true", help="Loop every 2 min (PM2 mode)")
    parser.add_argument("--health", action="store_true", help="Print health and exit")
    args = parser.parse_args()

    if args.health:
        print(json.dumps(health(), indent=2))
        return

    print("=" * 58)
    print(f"  Cloud Orchestrator — {AGENT_ID}")
    print(f"  Vault : {VAULT_DIR}")
    print(f"  Mode  : {'watch' if args.watch else 'once'}")
    print("=" * 58)

    log("orchestrator_started", {"mode": "watch" if args.watch else "once"})

    if not args.watch:
        run_once()
        return

    print(f"  Polling /Needs_Action every {WATCH_INTERVAL}s. Ctrl+C to stop.\n")
    try:
        while True:
            run_once()
            time.sleep(WATCH_INTERVAL)
    except KeyboardInterrupt:
        log("orchestrator_stopped", {"reason": "keyboard_interrupt"})
        print(f"\n[{AGENT_ID}] Stopped.")


if __name__ == "__main__":
    main()
