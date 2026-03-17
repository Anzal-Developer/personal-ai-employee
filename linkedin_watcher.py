#!/usr/bin/env python3
"""
LinkedIn Watcher — AI Employee Silver Tier
Uses Playwright to scrape LinkedIn notifications and messages,
then routes new items into AI_Employee_Vault/Needs_Action/ as LINKEDIN_*.md files.

Usage:
    uv run linkedin_watcher.py           # Run continuously (every 15 min)
    uv run linkedin_watcher.py --once    # Run once (for cron)
    uv run linkedin_watcher.py --setup   # First-time login (saves session)

Requirements:
    uv add playwright && uv run playwright install chromium
"""

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ── Config ────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent.resolve()
VAULT_DIR = BASE_DIR / "AI_Employee_Vault"
NEEDS_ACTION_DIR = VAULT_DIR / "Needs_Action"
LOGS_DIR = VAULT_DIR / "Logs"
SESSION_FILE = BASE_DIR / "linkedin_session.json"
PROCESSED_FILE = VAULT_DIR / "Logs" / "linkedin_processed.json"

POLL_INTERVAL_SECONDS = 900  # 15 minutes
LINKEDIN_URL = "https://www.linkedin.com"


# ── Helpers ───────────────────────────────────────────────────────────────────

def log_action(action: str, details: dict):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"{today}.jsonl"
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "action": action, **details}
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"[LOG] {entry}")


def slugify(text: str, max_len: int = 50) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[\s_-]+", "_", text).strip("_")
    return text[:max_len]


def detect_priority(text: str) -> str:
    text = text.lower()
    if any(k in text for k in ("urgent", "asap", "payment", "invoice", "contract", "waiting")):
        return "high"
    if any(k in text for k in ("connect", "message", "replied", "mentioned")):
        return "medium"
    return "low"


def load_processed() -> set:
    if PROCESSED_FILE.exists():
        return set(json.loads(PROCESSED_FILE.read_text()))
    return set()


def save_processed(ids: set):
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_FILE.write_text(json.dumps(list(ids)))


def create_vault_entry(item_type: str, sender: str, subject: str, snippet: str, item_id: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = slugify(subject)
    filename = f"LINKEDIN_{timestamp}_{slug}.md"
    filepath = NEEDS_ACTION_DIR / filename
    priority = detect_priority(subject + " " + snippet)

    content = f"""---
type: linkedin_{item_type}
from: {sender}
subject: "{subject}"
received_at: {datetime.now(timezone.utc).isoformat()}
snippet: "{snippet[:200]}"
item_id: "{item_id}"
priority: {priority}
status: pending
---

# LinkedIn {item_type.title()}: {subject}

## From
{sender}

## Preview
{snippet}

## Instructions for AI Employee

1. Read `Company_Handbook.md` to determine the correct action.
2. If this is a **message**: draft a reply and create approval request in `/Pending_Approval`.
3. If this is a **connection request**: note it, move to Done (accept/ignore on LinkedIn directly).
4. If this is a **notification**: summarize and move to Done.
5. Log the action and update `Dashboard.md`.
"""
    NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content, encoding="utf-8")
    return filepath


# ── Playwright Scrapers ───────────────────────────────────────────────────────

def save_session(page):
    """Save browser cookies/storage for reuse."""
    storage = page.context.storage_state()
    SESSION_FILE.write_text(json.dumps(storage))
    print(f"[LINKEDIN] Session saved to {SESSION_FILE}")


def is_logged_in(page) -> bool:
    try:
        page.wait_for_selector("nav.global-nav", timeout=5000)
        return True
    except PlaywrightTimeout:
        return False


def login_and_save_session(playwright):
    """Interactive login — user logs in manually, session is saved."""
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    print("[LINKEDIN] Opening LinkedIn for manual login...")
    print("[LINKEDIN] Log in with your credentials, then press Enter here.")
    page.goto(LINKEDIN_URL)
    input("\n[LINKEDIN] Press Enter after you have logged in successfully: ")

    save_session(page)
    browser.close()
    print("[LINKEDIN] Setup complete. Run with --once or without flags to start watching.")


def scrape_notifications(page) -> list:
    """Scrape recent LinkedIn notifications."""
    items = []
    try:
        page.goto(f"{LINKEDIN_URL}/notifications/", timeout=15000)
        page.wait_for_selector(".notification-item, .nt-card", timeout=8000)

        cards = page.query_selector_all(".notification-item, .nt-card, [data-test-notification-card]")
        for card in cards[:10]:
            text = card.inner_text().strip().replace("\n", " ")[:300]
            item_id = card.get_attribute("data-urn") or card.get_attribute("id") or slugify(text, 30)
            if text:
                items.append({
                    "type": "notification",
                    "sender": "LinkedIn",
                    "subject": text[:80],
                    "snippet": text,
                    "id": item_id,
                })
    except PlaywrightTimeout:
        print("[LINKEDIN] Timed out loading notifications — skipping.")
    return items


def scrape_messages(page) -> list:
    """Scrape recent LinkedIn messages."""
    items = []
    try:
        page.goto(f"{LINKEDIN_URL}/messaging/", timeout=15000)
        page.wait_for_selector(".msg-conversation-listitem, .msg-conversations-container", timeout=8000)

        convos = page.query_selector_all(".msg-conversation-listitem")
        for convo in convos[:5]:
            try:
                name_el = convo.query_selector(".msg-conversation-listitem__participant-names")
                preview_el = convo.query_selector(".msg-conversation-listitem__message-snippet")
                unread_el = convo.query_selector(".msg-conversation-listitem__unread-count")

                if not unread_el:
                    continue  # Skip read conversations

                sender = name_el.inner_text().strip() if name_el else "Unknown"
                preview = preview_el.inner_text().strip() if preview_el else ""
                item_id = convo.get_attribute("data-urn") or slugify(sender + preview, 30)

                items.append({
                    "type": "message",
                    "sender": sender,
                    "subject": f"Message from {sender}",
                    "snippet": preview,
                    "id": item_id,
                })
            except Exception:
                continue
    except PlaywrightTimeout:
        print("[LINKEDIN] Timed out loading messages — skipping.")
    return items


def poll_once():
    """Single LinkedIn poll — check notifications and messages."""
    print(f"[LINKEDIN] Polling at {datetime.now(timezone.utc).isoformat()}")

    if not SESSION_FILE.exists():
        print("[LINKEDIN] No session found. Run with --setup first to log in.")
        return

    processed = load_processed()
    new_count = 0

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(BASE_DIR / "linkedin_profile"),
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )

        # Restore saved session
        storage = json.loads(SESSION_FILE.read_text())
        context.add_cookies(storage.get("cookies", []))

        page = context.new_page()
        page.goto(LINKEDIN_URL, timeout=15000)

        if not is_logged_in(page):
            print("[LINKEDIN] Session expired. Run with --setup to re-login.")
            context.close()
            return

        # Scrape notifications + messages
        all_items = scrape_notifications(page) + scrape_messages(page)
        context.close()

    for item in all_items:
        if item["id"] in processed:
            continue

        filepath = create_vault_entry(
            item_type=item["type"],
            sender=item["sender"],
            subject=item["subject"],
            snippet=item["snippet"],
            item_id=item["id"],
        )
        processed.add(item["id"])
        new_count += 1

        log_action("linkedin_received", {
            "type": item["type"],
            "from": item["sender"],
            "subject": item["subject"][:60],
            "vault_file": filepath.name,
            "priority": detect_priority(item["subject"] + item["snippet"]),
        })

        print(f"[LINKEDIN] Routed: {item['subject'][:60]} → {filepath.name}")

    save_processed(processed)

    if new_count == 0:
        print("[LINKEDIN] No new items.")
    else:
        print(f"[LINKEDIN] {new_count} new item(s) routed to Needs_Action/")

    log_action("linkedin_poll_complete", {"new_items": new_count})


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AI Employee LinkedIn Watcher")
    parser.add_argument("--once", action="store_true", help="Poll once and exit")
    parser.add_argument("--setup", action="store_true", help="First-time login setup")
    args = parser.parse_args()

    print("=" * 60)
    print("  AI Employee — LinkedIn Watcher")
    print("=" * 60)

    if args.setup:
        with sync_playwright() as p:
            login_and_save_session(p)
        return

    log_action("linkedin_watcher_started", {"mode": "once" if args.once else "continuous"})

    if args.once:
        poll_once()
    else:
        print(f"  Polling every {POLL_INTERVAL_SECONDS // 60} minutes. Ctrl+C to stop.\n")
        try:
            while True:
                poll_once()
                time.sleep(POLL_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            log_action("linkedin_watcher_stopped", {"reason": "keyboard_interrupt"})
            print("\n[LINKEDIN] Stopped.")


if __name__ == "__main__":
    main()
