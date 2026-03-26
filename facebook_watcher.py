#!/usr/bin/env python3
"""
Facebook Watcher — AI Employee Gold Tier
Monitors Facebook notifications and messages using Playwright.
Routes new items to /Needs_Action as FACEBOOK_*.md files for Claude to process.

Usage:
    uv run facebook_watcher.py           # Watch continuously (every 5 min)
    uv run facebook_watcher.py --once    # Check once and exit
    uv run facebook_watcher.py --setup   # Manual login + save session

Session:
    First run: uv run facebook_watcher.py --setup
    Log in via the browser, then press Enter. Session is saved to facebook_session.json.
"""

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ── Config ─────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent.resolve()
VAULT_DIR = BASE_DIR / "AI_Employee_Vault"
NEEDS_ACTION_DIR = VAULT_DIR / "Needs_Action"
LOGS_DIR = VAULT_DIR / "Logs"
FB_PROFILE_DIR = BASE_DIR / "facebook_profile"
FB_SESSION_FILE = BASE_DIR / "facebook_session.json"
SEEN_FILE = BASE_DIR / "facebook_seen.json"

CHECK_INTERVAL_SECONDS = 300  # 5 minutes


# ── Helpers ────────────────────────────────────────────────────────────────────

def log_action(action: str, details: dict):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"{today}.jsonl"
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "action": action, **details}
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"[LOG] {entry}")


def load_seen() -> set:
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()


def save_seen(seen: set):
    SEEN_FILE.write_text(json.dumps(list(seen)))


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower())[:50].strip("_")


def create_needs_action_file(item_type: str, title: str, body: str, url: str = "") -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = slugify(title)
    filename = f"FACEBOOK_{ts}_{slug}.md"
    filepath = NEEDS_ACTION_DIR / filename

    content = f"""---
type: facebook_{item_type}
source: Facebook
title: {title}
received: {datetime.now(timezone.utc).isoformat()}
url: {url}
status: pending
priority: medium
---

## Facebook {item_type.title()}: {title}

{body}

## Suggested Actions
- [ ] Review and classify this {item_type}
- [ ] Draft a response if needed (requires approval before sending)
- [ ] Log for CEO briefing summary
"""
    NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content, encoding="utf-8")
    print(f"[WATCHER] Created: {filename}")
    return filepath


# ── Setup: save session ────────────────────────────────────────────────────────

def setup_session():
    FB_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    print("[SETUP] Opening Facebook for manual login...")
    print("[SETUP] Log in via the browser, then press Enter here.")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(FB_PROFILE_DIR),
            headless=False,
            args=["--no-sandbox"],
        )
        page = context.new_page()
        page.goto("https://www.facebook.com/", timeout=30000)
        input("[SETUP] Press Enter after logging in to Facebook...")

        cookies = context.cookies()
        FB_SESSION_FILE.write_text(json.dumps({"cookies": cookies}, indent=2))
        print(f"[SETUP] Session saved ({len(cookies)} cookies)")
        context.close()


# ── Scraping ───────────────────────────────────────────────────────────────────

def scrape_facebook(seen: set) -> list[dict]:
    """Open Facebook, scrape notifications and messages, return new items."""
    if not FB_SESSION_FILE.exists():
        print("[WATCHER] No session file found. Run: uv run facebook_watcher.py --setup")
        return []

    FB_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    items = []

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(FB_PROFILE_DIR),
            headless=True,
            args=["--no-sandbox"],
        )

        # Inject session cookies
        storage = json.loads(FB_SESSION_FILE.read_text())
        context.add_cookies(storage.get("cookies", []))
        page = context.new_page()

        try:
            page.goto("https://www.facebook.com/", timeout=30000)
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(3000)

            current_url = page.url
            if "login" in current_url or "checkpoint" in current_url:
                print("[WATCHER] Session expired — re-run: uv run facebook_watcher.py --setup")
                context.close()
                return []

            print(f"[WATCHER] Logged in. URL: {current_url}")

            # ── Scrape Notifications ───────────────────────────────────────
            try:
                page.goto("https://www.facebook.com/notifications/", timeout=20000)
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(3000)

                # Extract notification text using JS
                notifs = page.evaluate("""() => {
                    const results = [];
                    const links = document.querySelectorAll('a[href*="/notification/"]');
                    for (const link of Array.from(links).slice(0, 15)) {
                        const text = link.innerText || link.textContent;
                        const href = link.href;
                        if (text && text.trim().length > 5) {
                            results.push({ text: text.trim().slice(0, 300), url: href });
                        }
                    }
                    return results;
                }""")

                for notif in notifs:
                    key = f"notif:{notif['url']}"
                    if key not in seen and notif["text"]:
                        items.append({
                            "type": "notification",
                            "title": notif["text"][:80],
                            "body": notif["text"],
                            "url": notif["url"],
                            "key": key,
                        })
                        seen.add(key)

                print(f"[WATCHER] Found {len(notifs)} notifications, {sum(1 for i in items if i['type']=='notification')} new")

            except Exception as e:
                print(f"[WATCHER] Notification scrape error: {e}")

            # ── Scrape Messages ────────────────────────────────────────────
            try:
                page.goto("https://www.facebook.com/messages/", timeout=20000)
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(4000)

                # Extract conversation previews
                convos = page.evaluate("""() => {
                    const results = [];
                    // Look for unread conversation threads
                    const rows = document.querySelectorAll('[role="row"], [role="listitem"]');
                    for (const row of Array.from(rows).slice(0, 10)) {
                        const text = row.innerText || '';
                        if (text.trim().length < 5) continue;
                        const link = row.querySelector('a');
                        results.push({
                            text: text.trim().slice(0, 300),
                            url: link ? link.href : ''
                        });
                    }
                    return results;
                }""")

                for convo in convos:
                    key = f"msg:{convo.get('url', convo['text'][:50])}"
                    if key not in seen and convo["text"]:
                        items.append({
                            "type": "message",
                            "title": convo["text"][:80],
                            "body": convo["text"],
                            "url": convo.get("url", ""),
                            "key": key,
                        })
                        seen.add(key)

                print(f"[WATCHER] Found {len(convos)} message threads")

            except Exception as e:
                print(f"[WATCHER] Message scrape error: {e}")

        except Exception as e:
            print(f"[WATCHER] Scrape error: {e}")
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            try:
                shot = LOGS_DIR / f"fb_watcher_error_{ts}.png"
                page.screenshot(path=str(shot))
                print(f"[WATCHER] Error screenshot: {shot}")
            except Exception:
                pass

        context.close()

    return items


# ── Main ───────────────────────────────────────────────────────────────────────

def check_facebook():
    seen = load_seen()
    items = scrape_facebook(seen)

    created = 0
    for item in items:
        create_needs_action_file(
            item_type=item["type"],
            title=item["title"],
            body=item["body"],
            url=item.get("url", ""),
        )
        created += 1

    save_seen(seen)

    if created:
        log_action("facebook_items_detected", {"new_items": created})
    else:
        print("[WATCHER] No new Facebook items.")

    return created


def main():
    parser = argparse.ArgumentParser(description="Facebook Watcher — AI Employee Gold Tier")
    parser.add_argument("--once", action="store_true", help="Check once and exit")
    parser.add_argument("--setup", action="store_true", help="Manual login + save session")
    args = parser.parse_args()

    if args.setup:
        setup_session()
        return

    print("=" * 60)
    print("  AI Employee — Facebook Watcher")
    print("=" * 60)
    print(f"  Vault:  {VAULT_DIR}")
    print(f"  Mode:   {'once' if args.once else f'continuous every {CHECK_INTERVAL_SECONDS}s'}")
    print("=" * 60)
    print()

    if args.once:
        check_facebook()
        return

    log_action("facebook_watcher_started", {"interval": CHECK_INTERVAL_SECONDS})
    print(f"  Checking Facebook every {CHECK_INTERVAL_SECONDS}s. Ctrl+C to stop.\n")

    try:
        while True:
            print(f"[WATCHER] Checking at {datetime.now().strftime('%H:%M:%S')}...")
            check_facebook()
            time.sleep(CHECK_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        log_action("facebook_watcher_stopped", {"reason": "keyboard_interrupt"})
        print("\n[WATCHER] Stopped.")


if __name__ == "__main__":
    main()
