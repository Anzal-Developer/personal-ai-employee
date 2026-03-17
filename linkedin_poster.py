#!/usr/bin/env python3
"""
LinkedIn Auto-Poster — AI Employee Silver Tier
Watches /Approved for LINKEDIN_POST_*.md files and publishes them to LinkedIn
using the saved Playwright session. Human-in-the-loop: post only after approval.

Usage:
    uv run linkedin_poster.py           # Watch /Approved continuously
    uv run linkedin_poster.py --once    # Check /Approved once and exit
    uv run linkedin_poster.py --dry-run # Preview post without publishing

Flow:
    1. Draft saved to /Pending_Approval/LINKEDIN_POST_*.md
    2. Human reviews and moves file to /Approved
    3. This script detects the file, extracts post text, publishes to LinkedIn
    4. Archives to /Done and logs the action
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
APPROVED_DIR = VAULT_DIR / "Approved"
DONE_DIR = VAULT_DIR / "Done"
LOGS_DIR = VAULT_DIR / "Logs"
SESSION_FILE = BASE_DIR / "linkedin_session.json"

POLL_INTERVAL_SECONDS = 30  # check /Approved every 30 seconds


# ── Helpers ───────────────────────────────────────────────────────────────────

def log_action(action: str, details: dict):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"{today}.jsonl"
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "action": action, **details}
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"[LOG] {entry}")


def extract_post_text(filepath: Path) -> str:
    """Extract the post body between the two --- separators after frontmatter."""
    content = filepath.read_text(encoding="utf-8")

    # Strip YAML frontmatter (first --- block)
    parts = content.split("---")
    # parts[0] = empty, parts[1] = frontmatter, parts[2+] = body
    body = "---".join(parts[2:]).strip() if len(parts) >= 3 else content.strip()

    # Extract text between first pair of --- in body (the post itself)
    post_match = re.search(r"## Proposed LinkedIn Post\s*\n\s*-{3,}\s*\n(.*?)\n\s*-{3,}", body, re.DOTALL)
    if post_match:
        return post_match.group(1).strip()

    # Fallback: everything before "## Character count"
    fallback = re.split(r"\n##\s+Character count", body)[0]
    # Remove the "## Proposed LinkedIn Post" header
    fallback = re.sub(r"^##\s+Proposed LinkedIn Post\s*\n", "", fallback).strip()
    return fallback


def get_approved_posts() -> list[Path]:
    """Return all LINKEDIN_POST_*.md files in /Approved."""
    if not APPROVED_DIR.exists():
        return []
    return sorted(APPROVED_DIR.glob("LINKEDIN_POST_*.md"))


# ── Playwright Publisher ──────────────────────────────────────────────────────

def publish_post(post_text: str, dry_run: bool = False) -> bool:
    """Use Playwright + saved session to publish the post on LinkedIn."""

    if not SESSION_FILE.exists():
        print("[POSTER] No LinkedIn session found. Run: uv run linkedin_watcher.py --setup")
        return False

    if dry_run:
        print("[POSTER] DRY RUN — post text that would be published:")
        print("-" * 60)
        print(post_text)
        print("-" * 60)
        return True

    print("[POSTER] Launching browser to publish LinkedIn post...")

    with sync_playwright() as p:
        # Launch with saved persistent profile
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(BASE_DIR / "linkedin_profile"),
            headless=False,   # visible so you can see it post
            slow_mo=500,
            args=["--no-sandbox"],
        )

        # Restore session cookies
        storage = json.loads(SESSION_FILE.read_text())
        context.add_cookies(storage.get("cookies", []))

        page = context.new_page()

        try:
            # Go to LinkedIn feed
            print("[POSTER] Navigating to LinkedIn feed...")
            page.goto("https://www.linkedin.com/feed/", timeout=20000)
            page.wait_for_load_state("domcontentloaded")

            # Check logged in
            try:
                page.wait_for_selector("div.share-box-feed-entry__top-bar, .share-creation-state__content, button[aria-label='Start a post']", timeout=10000)
            except PlaywrightTimeout:
                print("[POSTER] LinkedIn session may have expired. Re-run: uv run linkedin_watcher.py --setup")
                context.close()
                return False

            # Click "Start a post"
            print("[POSTER] Opening post composer...")
            start_post_btn = page.locator("button[aria-label='Start a post'], .share-box-feed-entry__top-bar").first
            start_post_btn.click()
            page.wait_for_timeout(2000)

            # Type post content
            print("[POSTER] Typing post content...")
            editor = page.locator(".ql-editor, div[role='textbox'][contenteditable='true'], .editor-content").first
            editor.wait_for(timeout=8000)
            editor.click()
            page.wait_for_timeout(500)
            editor.fill(post_text)
            page.wait_for_timeout(1500)

            # Take screenshot before posting
            screenshot_path = DONE_DIR / f"linkedin_post_screenshot_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.png"
            DONE_DIR.mkdir(exist_ok=True)
            page.screenshot(path=str(screenshot_path))
            print(f"[POSTER] Screenshot saved: {screenshot_path.name}")

            # Click Post button
            print("[POSTER] Clicking Post button...")
            post_btn = page.locator("button.share-actions__primary-action, button[aria-label='Post'], button:has-text('Post')").last
            post_btn.wait_for(timeout=5000)
            post_btn.click()
            page.wait_for_timeout(3000)

            # Confirm post appeared
            page.wait_for_load_state("networkidle", timeout=10000)
            print("[POSTER] Post published successfully!")
            context.close()
            return True

        except Exception as e:
            print(f"[POSTER] Error during posting: {e}")
            error_screenshot = LOGS_DIR / f"error_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.png"
            page.screenshot(path=str(error_screenshot))
            print(f"[POSTER] Error screenshot: {error_screenshot}")
            context.close()
            return False


# ── Main Loop ─────────────────────────────────────────────────────────────────

def process_approved_posts(dry_run: bool = False):
    """Check /Approved for posts and publish them."""
    posts = get_approved_posts()

    if not posts:
        print("[POSTER] No approved posts found.")
        return

    for post_file in posts:
        print(f"[POSTER] Found approved post: {post_file.name}")
        post_text = extract_post_text(post_file)

        if not post_text.strip():
            print(f"[POSTER] Could not extract post text from {post_file.name} — skipping.")
            continue

        print(f"[POSTER] Post preview ({len(post_text)} chars):\n{post_text[:200]}...")

        success = publish_post(post_text, dry_run=dry_run)

        if success:
            # Archive to Done
            DONE_DIR.mkdir(exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            dest = DONE_DIR / f"DONE_{ts}_PUBLISHED_{post_file.name}"
            post_file.rename(dest)

            log_action("linkedin_post_published", {
                "file": post_file.name,
                "chars": len(post_text),
                "result": "dry_run" if dry_run else "published",
            })
            print(f"[POSTER] Archived to: {dest.name}")
        else:
            log_action("linkedin_post_failed", {
                "file": post_file.name,
                "result": "failed",
            })


def main():
    parser = argparse.ArgumentParser(description="LinkedIn Auto-Poster with HITL approval")
    parser.add_argument("--once", action="store_true", help="Check /Approved once and exit")
    parser.add_argument("--dry-run", action="store_true", help="Preview post without publishing")
    args = parser.parse_args()

    print("=" * 60)
    print("  AI Employee — LinkedIn Auto-Poster")
    print("=" * 60)
    print(f"  Watching: {APPROVED_DIR}")
    print(f"  Mode:     {'dry-run' if args.dry_run else 'once' if args.once else 'continuous'}")
    print("=" * 60)
    print()

    if args.once or args.dry_run:
        process_approved_posts(dry_run=args.dry_run)
        return

    print(f"  Checking /Approved every {POLL_INTERVAL_SECONDS}s. Ctrl+C to stop.\n")
    log_action("linkedin_poster_started", {"mode": "continuous"})

    try:
        while True:
            process_approved_posts()
            time.sleep(POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        log_action("linkedin_poster_stopped", {"reason": "keyboard_interrupt"})
        print("\n[POSTER] Stopped.")


if __name__ == "__main__":
    main()
