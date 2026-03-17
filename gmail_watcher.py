#!/usr/bin/env python3
"""
Gmail Watcher — AI Employee Silver Tier
Polls Gmail inbox for unread messages and routes them into
AI_Employee_Vault/Needs_Action/ as GMAIL_*.md files for the AI to process.

Usage:
    python gmail_watcher.py          # Run continuously (polling every 5 min)
    python gmail_watcher.py --once   # Run once (for cron jobs)

Setup:
    1. Enable Gmail API at console.cloud.google.com
    2. Create OAuth 2.0 Desktop credentials
    3. Download as credentials.json in this directory
    4. pip install google-auth google-auth-oauthlib google-api-python-client watchdog
"""

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent.resolve()
VAULT_DIR = BASE_DIR / "AI_Employee_Vault"
NEEDS_ACTION_DIR = VAULT_DIR / "Needs_Action"
LOGS_DIR = VAULT_DIR / "Logs"
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "gmail_token.json"

POLL_INTERVAL_SECONDS = 300  # 5 minutes
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# ── Helpers ───────────────────────────────────────────────────────────────────


def log_action(action: str, details: dict):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"{today}.jsonl"
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "action": action, **details}
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"[LOG] {entry}")


def slugify(text: str, max_len: int = 40) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_-]+", "_", text).strip("_")
    return text[:max_len]


def detect_priority(subject: str, snippet: str) -> str:
    combined = (subject + " " + snippet).lower()
    if any(k in combined for k in ("urgent", "asap", "critical", "invoice", "payment", "contract", "legal")):
        return "high"
    if any(k in combined for k in ("follow up", "reminder", "deadline", "project")):
        return "medium"
    return "low"


def get_gmail_service():
    """Authenticate and return a Gmail API service object."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        print("[ERROR] Missing Google API packages. Run:")
        print("  pip install google-auth google-auth-oauthlib google-api-python-client")
        return None

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                print(f"[ERROR] credentials.json not found at {CREDENTIALS_FILE}")
                print("  Download it from Google Cloud Console → APIs & Services → Credentials")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def get_unread_emails(service, max_results: int = 10) -> list:
    """Fetch unread emails from Gmail inbox."""
    results = service.users().messages().list(
        userId="me",
        labelIds=["INBOX", "UNREAD"],
        maxResults=max_results
    ).execute()

    messages = results.get("messages", [])
    emails = []

    for msg in messages:
        msg_data = service.users().messages().get(
            userId="me",
            id=msg["id"],
            format="metadata",
            metadataHeaders=["From", "Subject", "Date"]
        ).execute()

        headers = {h["name"]: h["value"] for h in msg_data.get("payload", {}).get("headers", [])}
        snippet = msg_data.get("snippet", "")

        emails.append({
            "message_id": msg["id"],
            "thread_id": msg_data.get("threadId", ""),
            "from": headers.get("From", "Unknown"),
            "subject": headers.get("Subject", "(no subject)"),
            "date": headers.get("Date", ""),
            "snippet": snippet[:300],
        })

    return emails


def create_vault_entry(email: dict) -> Path:
    """Write a GMAIL_*.md file to Needs_Action for the AI to process."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = slugify(email["subject"])
    filename = f"GMAIL_{timestamp}_{slug}.md"
    filepath = NEEDS_ACTION_DIR / filename

    priority = detect_priority(email["subject"], email["snippet"])

    content = f"""---
type: gmail
from: {email['from']}
subject: "{email['subject']}"
received_at: {datetime.now(timezone.utc).isoformat()}
snippet: "{email['snippet'][:200]}"
thread_id: "{email['thread_id']}"
message_id: "{email['message_id']}"
priority: {priority}
status: pending
---

# Email: {email['subject']}

## From
{email['from']}

## Received
{email['date']}

## Preview
{email['snippet']}

## Instructions for AI Employee

1. Read `Company_Handbook.md` to determine the correct action.
2. Classify the email type (inquiry, invoice, notification, task, etc.)
3. If a reply is needed: draft it and create an approval request in `/Pending_Approval`.
4. If it's a notification/newsletter: summarize and move to `/Done`.
5. If it contains invoice/contract/payment keywords: escalate to high priority approval.
6. Log the action and update `Dashboard.md`.
"""
    NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content, encoding="utf-8")
    return filepath


def load_processed_ids() -> set:
    """Load set of already-processed Gmail message IDs to avoid duplicates."""
    state_file = VAULT_DIR / "Logs" / "gmail_processed.json"
    if state_file.exists():
        with open(state_file) as f:
            return set(json.load(f))
    return set()


def save_processed_ids(ids: set):
    state_file = VAULT_DIR / "Logs" / "gmail_processed.json"
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(state_file, "w") as f:
        json.dump(list(ids), f)


def poll_once():
    """Single poll cycle — check for new emails and route to vault."""
    print(f"[GMAIL] Polling at {datetime.now(timezone.utc).isoformat()}")

    service = get_gmail_service()
    if not service:
        return

    processed_ids = load_processed_ids()
    emails = get_unread_emails(service)
    new_count = 0

    for email in emails:
        if email["message_id"] in processed_ids:
            continue

        filepath = create_vault_entry(email)
        processed_ids.add(email["message_id"])
        new_count += 1

        log_action("gmail_received", {
            "from": email["from"],
            "subject": email["subject"],
            "message_id": email["message_id"],
            "vault_file": filepath.name,
            "priority": detect_priority(email["subject"], email["snippet"]),
        })

        print(f"[GMAIL] Routed: {email['subject'][:50]} → {filepath.name}")

    save_processed_ids(processed_ids)

    if new_count == 0:
        print("[GMAIL] No new emails.")
    else:
        print(f"[GMAIL] {new_count} new email(s) routed to Needs_Action/")

    log_action("gmail_poll_complete", {"new_emails": new_count})


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="AI Employee Gmail Watcher")
    parser.add_argument("--once", action="store_true", help="Poll once and exit (for cron)")
    args = parser.parse_args()

    print("=" * 60)
    print("  AI Employee — Gmail Watcher")
    print("=" * 60)
    print(f"  Vault:    {VAULT_DIR}")
    print(f"  Mode:     {'single poll' if args.once else f'continuous ({POLL_INTERVAL_SECONDS}s interval)'}")
    print("=" * 60)

    log_action("gmail_watcher_started", {"mode": "once" if args.once else "continuous"})

    if args.once:
        poll_once()
    else:
        print("  Press Ctrl+C to stop.\n")
        try:
            while True:
                poll_once()
                time.sleep(POLL_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            log_action("gmail_watcher_stopped", {"reason": "keyboard_interrupt"})
            print("\n[GMAIL] Stopped.")


if __name__ == "__main__":
    main()
