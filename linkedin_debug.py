#!/usr/bin/env python3
"""Debug script — dumps the HTML around the Start a post area and tries clicking it."""

import json
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).parent.resolve()
SESSION_FILE = BASE_DIR / "linkedin_session.json"
LOGS_DIR = BASE_DIR / "AI_Employee_Vault" / "Logs"

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir=str(BASE_DIR / "linkedin_profile"),
        headless=False,
        slow_mo=500,
        args=["--no-sandbox"],
    )
    storage = json.loads(SESSION_FILE.read_text())
    context.add_cookies(storage.get("cookies", []))

    page = context.new_page()
    page.goto("https://www.linkedin.com/feed/", timeout=20000)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(3000)

    # Dump HTML of the share box area
    html = page.evaluate("""() => {
        const el = document.querySelector('.share-box-feed-entry')
            || document.querySelector('[class*="share-box"]')
            || document.querySelector('[class*="share-creation"]');
        return el ? el.outerHTML.substring(0, 3000) : 'NOT FOUND — trying body snippet';
    }""")
    print("=== SHARE BOX HTML ===")
    print(html[:3000])

    # List all elements containing "Start a post"
    elements = page.evaluate("""() => {
        const results = [];
        document.querySelectorAll('*').forEach(el => {
            if (el.children.length === 0 && el.textContent.trim() === 'Start a post') {
                results.push({
                    tag: el.tagName,
                    className: el.className,
                    role: el.getAttribute('role'),
                    contenteditable: el.getAttribute('contenteditable'),
                    placeholder: el.getAttribute('placeholder'),
                    ariaLabel: el.getAttribute('aria-label'),
                    parentClass: el.parentElement ? el.parentElement.className : ''
                });
            }
        });
        return results;
    }""")
    print("\n=== ELEMENTS WITH 'Start a post' TEXT ===")
    for e in elements:
        print(e)

    # Try clicking the first result by evaluating
    print("\n=== ATTEMPTING CLICK ===")
    page.evaluate("""() => {
        let el = null;
        document.querySelectorAll('*').forEach(node => {
            if (!el && node.children.length === 0 && node.textContent.trim() === 'Start a post') {
                el = node;
            }
        });
        if (el) { el.click(); console.log('clicked:', el.tagName, el.className); }
        else { console.log('not found'); }
    }""")
    page.wait_for_timeout(3000)
    page.screenshot(path=str(LOGS_DIR / "debug_after_click.png"))
    print("Screenshot saved: debug_after_click.png")

    input("Press Enter to close browser...")
    context.close()
