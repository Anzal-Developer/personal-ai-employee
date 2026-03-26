#!/usr/bin/env python3
"""
Facebook Auto-Poster — AI Employee Gold Tier
Watches /Approved for FACEBOOK_POST_*.md files and publishes to Facebook
using a saved Playwright session. Human-in-the-loop: only posts after approval.

Usage:
    uv run facebook_poster.py           # Watch /Approved continuously
    uv run facebook_poster.py --once    # Check /Approved once and exit
    uv run facebook_poster.py --dry-run # Preview without posting
    uv run facebook_poster.py --setup   # Open browser for manual login + save session

Flow:
    1. /facebook-post skill drafts post → saves to /Pending_Approval/FACEBOOK_POST_*.md
    2. Human moves file to /Approved
    3. This script detects the file, publishes to Facebook, archives to /Done
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
APPROVED_DIR = VAULT_DIR / "Approved"
DONE_DIR = VAULT_DIR / "Done"
LOGS_DIR = VAULT_DIR / "Logs"
FB_PROFILE_DIR = BASE_DIR / "facebook_profile"
FB_SESSION_FILE = BASE_DIR / "facebook_session.json"

POLL_INTERVAL_SECONDS = 30


# ── Helpers ────────────────────────────────────────────────────────────────────

def log_action(action: str, details: dict):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"{today}.jsonl"
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "action": action, **details}
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"[LOG] {entry}")


def extract_post_text(filepath: Path) -> str:
    """Extract post body from FACEBOOK_POST_*.md frontmatter structure."""
    content = filepath.read_text(encoding="utf-8")
    parts = content.split("---")
    body = "---".join(parts[2:]).strip() if len(parts) >= 3 else content.strip()

    # Try to find the post block
    post_match = re.search(r"## Proposed Facebook Post\s*\n\s*-{3,}\s*\n(.*?)\n\s*-{3,}", body, re.DOTALL)
    if post_match:
        return post_match.group(1).strip()

    # Fallback: strip the header, take everything before ## Character count
    fallback = re.split(r"\n##\s+Character count", body)[0]
    fallback = re.sub(r"^##\s+Proposed Facebook Post\s*\n", "", fallback).strip()
    return fallback


def get_approved_posts() -> list[Path]:
    if not APPROVED_DIR.exists():
        return []
    return sorted(APPROVED_DIR.glob("FACEBOOK_POST_*.md"))


# ── Setup: save session ────────────────────────────────────────────────────────

def setup_session():
    """Open Facebook in a visible browser. Log in manually, then press Enter here."""
    FB_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    print("[SETUP] Opening Facebook for manual login...")
    print("[SETUP] Log in, then press Enter in this terminal to save session.")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(FB_PROFILE_DIR),
            headless=False,
            args=["--no-sandbox"],
        )
        page = context.new_page()
        page.goto("https://www.facebook.com/", timeout=30000)
        input("[SETUP] Press Enter after you've logged in to Facebook...")

        # Save cookies
        cookies = context.cookies()
        FB_SESSION_FILE.write_text(json.dumps({"cookies": cookies}, indent=2))
        print(f"[SETUP] Session saved to {FB_SESSION_FILE} ({len(cookies)} cookies)")
        context.close()


# ── Publisher ──────────────────────────────────────────────────────────────────

def publish_post(post_text: str, dry_run: bool = False) -> bool:
    """Publish a post to Facebook using Playwright + saved session."""

    if dry_run:
        print("[POSTER] DRY RUN — post text:")
        print("-" * 60)
        print(post_text)
        print("-" * 60)
        return True

    if not FB_SESSION_FILE.exists():
        print("[POSTER] No Facebook session found. Run: uv run facebook_poster.py --setup")
        return False

    FB_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    print("[POSTER] Launching browser to publish Facebook post...")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(FB_PROFILE_DIR),
            headless=False,
            slow_mo=400,
            args=["--no-sandbox"],
        )

        # Inject saved session cookies
        storage = json.loads(FB_SESSION_FILE.read_text())
        context.add_cookies(storage.get("cookies", []))

        page = context.new_page()

        try:
            print("[POSTER] Navigating to Facebook...")
            page.goto("https://www.facebook.com/", timeout=30000)
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(3000)

            # Reload with cookies injected
            context.add_cookies(storage.get("cookies", []))
            page.reload(timeout=20000)
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(3000)

            current_url = page.url
            print(f"[POSTER] Current URL: {current_url}")

            # Check login by URL
            if "login" in current_url or "checkpoint" in current_url:
                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                shot = LOGS_DIR / f"fb_login_failed_{ts}.png"
                page.screenshot(path=str(shot))
                print(f"[POSTER] Not logged in — session expired. Screenshot: {shot}")
                print("[POSTER] Re-run: uv run facebook_poster.py --setup")
                context.close()
                return False

            print("[POSTER] Login confirmed. Looking for post composer...")

            # Click the "What's on your mind?" post box to open the composer modal.
            # Facebook's actual aria-label is "Create a post"; placeholder includes the user's
            # name ("What's on your mind, M Anzal?") so we match with contains, not exact.
            clicked = False

            # Approach 1: aria-label "Create a post" (the real FB attribute)
            if not clicked:
                try:
                    loc = page.locator("[aria-label='Create a post']").first
                    loc.click(timeout=8000)
                    page.wait_for_timeout(3000)
                    if page.locator("[contenteditable='true']").count() > 0 or page.locator("[role='dialog']").count() > 0:
                        print("[POSTER] Composer opened via aria-label='Create a post'.")
                        clicked = True
                except Exception as e:
                    print(f"[POSTER] Approach 1 failed: {e}")

            # Approach 2: placeholder contains "What's on your mind"  (name-aware)
            if not clicked:
                try:
                    loc = page.get_by_placeholder("What's on your mind").first
                    loc.click(timeout=8000)
                    page.wait_for_timeout(3000)
                    if page.locator("[contenteditable='true']").count() > 0 or page.locator("[role='dialog']").count() > 0:
                        print("[POSTER] Composer opened via placeholder.")
                        clicked = True
                except Exception as e:
                    print(f"[POSTER] Approach 2 failed: {e}")

            # Approach 3: JS — click the span/div whose text starts with "What's on your mind"
            if not clicked:
                try:
                    page.evaluate("""() => {
                        const needle = "What's on your mind";
                        // Try role=button elements first
                        for (const el of document.querySelectorAll('[role="button"]')) {
                            if (el.innerText && el.innerText.includes(needle)) {
                                el.click(); return;
                            }
                        }
                        // Fallback: any span or div containing the text
                        for (const el of document.querySelectorAll('span, div')) {
                            if (el.children.length === 0 && el.innerText && el.innerText.includes(needle)) {
                                el.parentElement && el.parentElement.click();
                                return;
                            }
                        }
                    }""")
                    page.wait_for_timeout(4000)
                    if page.locator("[contenteditable='true']").count() > 0 or page.locator("[role='dialog']").count() > 0:
                        print("[POSTER] Composer opened via JS text walk.")
                        clicked = True
                    else:
                        print("[POSTER] Approach 3 JS ran but no editor detected.")
                except Exception as e:
                    print(f"[POSTER] Approach 3 failed: {e}")

            # Approach 4: Playwright get_by_role button named "Create a post"
            if not clicked:
                try:
                    loc = page.get_by_role("button", name="Create a post").first
                    loc.click(timeout=8000)
                    page.wait_for_timeout(3000)
                    if page.locator("[contenteditable='true']").count() > 0 or page.locator("[role='dialog']").count() > 0:
                        print("[POSTER] Composer opened via get_by_role.")
                        clicked = True
                except Exception as e:
                    print(f"[POSTER] Approach 4 failed: {e}")

            # Screenshot after click attempts
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            shot = LOGS_DIR / f"fb_after_click_{ts}.png"
            page.screenshot(path=str(shot))
            print(f"[POSTER] Post-click screenshot: {shot}")

            if not clicked:
                print("[POSTER] Could not open Facebook post composer.")
                context.close()
                return False

            # Find the contenteditable editor (modal or inline)
            editor = None
            EDITOR_SELECTORS = [
                "[contenteditable='true'][role='textbox']",
                "[contenteditable='true']",
            ]
            for sel in EDITOR_SELECTORS:
                try:
                    loc = page.locator(sel).last
                    loc.wait_for(timeout=8000)
                    editor = loc
                    print(f"[POSTER] Editor found: {sel}")
                    break
                except PlaywrightTimeout:
                    print(f"[POSTER] Editor not found: {sel}")

            if editor is None:
                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                shot = LOGS_DIR / f"fb_no_editor_{ts}.png"
                page.screenshot(path=str(shot))
                print(f"[POSTER] Could not find text editor. Screenshot: {shot}")
                context.close()
                return False

            editor.click()
            page.wait_for_timeout(500)
            editor.fill(post_text)
            page.wait_for_timeout(1500)

            # Screenshot before posting
            DONE_DIR.mkdir(exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            pre_shot = DONE_DIR / f"fb_post_screenshot_{ts}.png"
            page.screenshot(path=str(pre_shot))
            print(f"[POSTER] Pre-post screenshot: {pre_shot.name}")

            # Click the Post button
            posted = False
            POST_BTN_SELECTORS = [
                "[aria-label='Post']",
                "button:has-text('Post')",
                "[data-testid='react-composer-post-button']",
            ]
            for sel in POST_BTN_SELECTORS:
                try:
                    btn = page.locator(sel).last
                    btn.wait_for(timeout=8000)
                    btn.click()
                    print(f"[POSTER] Post button clicked via: {sel}")
                    posted = True
                    break
                except PlaywrightTimeout:
                    print(f"[POSTER] Post button not found: {sel}")

            if not posted:
                # Fallback: JS click on Post button
                try:
                    page.evaluate("""() => {
                        for (const btn of document.querySelectorAll('div[role="button"]')) {
                            if (btn.textContent.trim() === 'Post') { btn.click(); return; }
                        }
                    }""")
                    page.wait_for_timeout(2000)
                    posted = True
                    print("[POSTER] Post button clicked via JS fallback.")
                except Exception as e:
                    print(f"[POSTER] JS fallback failed: {e}")

            if not posted:
                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                shot = LOGS_DIR / f"fb_no_post_btn_{ts}.png"
                page.screenshot(path=str(shot))
                print(f"[POSTER] Could not find Post button. Screenshot: {shot}")
                context.close()
                return False

            page.wait_for_timeout(4000)
            print("[POSTER] Facebook post published successfully!")
            context.close()
            return True

        except Exception as e:
            print(f"[POSTER] Unexpected error: {e}")
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            shot = LOGS_DIR / f"fb_error_{ts}.png"
            try:
                page.screenshot(path=str(shot))
                print(f"[POSTER] Error screenshot: {shot}")
            except Exception:
                pass
            context.close()
            return False


# ── Main loop ──────────────────────────────────────────────────────────────────

def process_approved_posts(dry_run: bool = False):
    posts = get_approved_posts()
    if not posts:
        print("[POSTER] No approved Facebook posts found.")
        return

    for post_file in posts:
        print(f"[POSTER] Found approved post: {post_file.name}")
        post_text = extract_post_text(post_file)

        if not post_text.strip():
            print(f"[POSTER] Could not extract text from {post_file.name} — skipping.")
            continue

        print(f"[POSTER] Post preview ({len(post_text)} chars):\n{post_text[:200]}...")

        success = publish_post(post_text, dry_run=dry_run)

        if success:
            DONE_DIR.mkdir(exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            dest = DONE_DIR / f"DONE_{ts}_PUBLISHED_{post_file.name}"
            post_file.rename(dest)
            log_action("facebook_post_published", {
                "file": post_file.name,
                "chars": len(post_text),
                "result": "dry_run" if dry_run else "published",
            })
            print(f"[POSTER] Archived to: {dest.name}")
        else:
            log_action("facebook_post_failed", {"file": post_file.name, "result": "failed"})


def main():
    parser = argparse.ArgumentParser(description="Facebook Auto-Poster with HITL approval")
    parser.add_argument("--once", action="store_true", help="Check /Approved once and exit")
    parser.add_argument("--dry-run", action="store_true", help="Preview post without publishing")
    parser.add_argument("--setup", action="store_true", help="Open browser for manual login")
    args = parser.parse_args()

    if args.setup:
        setup_session()
        return

    print("=" * 60)
    print("  AI Employee — Facebook Auto-Poster")
    print("=" * 60)
    print(f"  Watching: {APPROVED_DIR}")
    print(f"  Mode:     {'dry-run' if args.dry_run else 'once' if args.once else 'continuous'}")
    print("=" * 60)
    print()

    if args.once or args.dry_run:
        process_approved_posts(dry_run=args.dry_run)
        return

    log_action("facebook_poster_started", {"mode": "continuous"})
    print(f"  Checking /Approved every {POLL_INTERVAL_SECONDS}s. Ctrl+C to stop.\n")

    try:
        while True:
            process_approved_posts()
            time.sleep(POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        log_action("facebook_poster_stopped", {"reason": "keyboard_interrupt"})
        print("\n[POSTER] Stopped.")


if __name__ == "__main__":
    main()
