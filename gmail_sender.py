#!/usr/bin/env python3
"""
Gmail Sender — AI Employee Silver Tier (MCP-style external action tool)
Sends approved emails via Gmail API. Called by the send-email skill after
a human has moved an approval file to /Approved.

Usage:
    python gmail_sender.py --to "recipient@example.com" --subject "Hello" --body "Message"
    python gmail_sender.py --approved-file "AI_Employee_Vault/Approved/REPLY_*.md"

Setup:
    Same credentials.json as gmail_watcher.py (needs gmail.send scope)
    pip install google-auth google-auth-oauthlib google-api-python-client
"""

import argparse
import base64
import json
import re
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
VAULT_DIR = BASE_DIR / "AI_Employee_Vault"
LOGS_DIR = VAULT_DIR / "Logs"
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "gmail_send_token.json"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]


def log_action(action: str, details: dict):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"{today}.jsonl"
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "action": action, **details}
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"[LOG] {entry}")


def get_gmail_service():
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        print("[ERROR] Missing packages. Run: pip install google-auth google-auth-oauthlib google-api-python-client")
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
                return None
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0, open_browser=False)

        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def send_email(to: str, subject: str, body: str, thread_id: str = None) -> bool:
    """Send an email via Gmail API."""
    service = get_gmail_service()
    if not service:
        return False

    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    msg_body = {"raw": raw}
    if thread_id:
        msg_body["threadId"] = thread_id

    try:
        result = service.users().messages().send(userId="me", body=msg_body).execute()
        print(f"[SENDER] Email sent. Message ID: {result['id']}")
        log_action("email_sent", {"to": to, "subject": subject, "message_id": result["id"], "result": "success"})
        return True
    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}")
        log_action("email_failed", {"to": to, "subject": subject, "error": str(e)})
        return False


def parse_approved_file(filepath: Path) -> dict:
    """Parse frontmatter and body from an approved email .md file."""
    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")

    frontmatter = {}
    body_lines = []
    in_frontmatter = False
    frontmatter_done = False
    dash_count = 0

    for line in lines:
        if line.strip() == "---":
            dash_count += 1
            if dash_count == 1:
                in_frontmatter = True
            elif dash_count == 2:
                in_frontmatter = False
                frontmatter_done = True
            continue

        if in_frontmatter:
            if ":" in line:
                key, _, val = line.partition(":")
                frontmatter[key.strip()] = val.strip().strip('"')
        elif frontmatter_done:
            body_lines.append(line)

    # Extract just the "Proposed Reply" section if present
    body = "\n".join(body_lines).strip()
    proposed_match = re.search(r"## Proposed Reply\s*\n(.*?)(?=\n##|\Z)", body, re.DOTALL)
    if proposed_match:
        body = proposed_match.group(1).strip()

    return {
        "to": frontmatter.get("to", ""),
        "subject": frontmatter.get("subject", ""),
        "thread_id": frontmatter.get("thread_id", ""),
        "body": body,
    }


def main():
    parser = argparse.ArgumentParser(description="AI Employee Gmail Sender")
    parser.add_argument("--to", help="Recipient email address")
    parser.add_argument("--subject", help="Email subject")
    parser.add_argument("--body", help="Email body text")
    parser.add_argument("--thread-id", help="Gmail thread ID for replies")
    parser.add_argument("--approved-file", help="Path to an approved .md file to send")
    args = parser.parse_args()

    if args.approved_file:
        filepath = Path(args.approved_file)
        if not filepath.exists():
            print(f"[ERROR] File not found: {filepath}")
            return

        email_data = parse_approved_file(filepath)
        print(f"[SENDER] Sending from approved file: {filepath.name}")
        print(f"  To:      {email_data['to']}")
        print(f"  Subject: {email_data['subject']}")
        success = send_email(
            to=email_data["to"],
            subject=email_data["subject"],
            body=email_data["body"],
            thread_id=email_data.get("thread_id"),
        )

        if success:
            # Archive to Done
            done_dir = VAULT_DIR / "Done"
            done_dir.mkdir(exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            dest = done_dir / f"DONE_{ts}_SENT_{filepath.stem}.md"
            filepath.rename(dest)
            print(f"[SENDER] Archived to: {dest.name}")

    elif args.to and args.subject and args.body:
        send_email(to=args.to, subject=args.subject, body=args.body, thread_id=args.thread_id)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
