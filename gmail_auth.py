#!/usr/bin/env python3
"""
Gmail OAuth2 Authorization Helper — WSL copy-paste flow (no PKCE).
Run this once to generate gmail_token.json.

Usage:
    uv run gmail_auth.py
"""

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "gmail_token.json"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]
REDIRECT_URI = "http://localhost"


def main():
    print("=" * 60)
    print("  Gmail OAuth2 Authorization (WSL copy-paste)")
    print("=" * 60)

    # Load client credentials
    creds_data = json.loads(CREDENTIALS_FILE.read_text())["installed"]
    client_id = creds_data["client_id"]
    client_secret = creds_data["client_secret"]
    token_uri = creds_data["token_uri"]

    # Build auth URL manually (no PKCE)
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = "https://accounts.google.com/o/oauth2/auth?" + urllib.parse.urlencode(params)

    print("\nSTEP 1 — Open this URL in your Windows browser:\n")
    print(f"   {auth_url}\n")
    print("STEP 2 — Sign in with your Gmail account and click Allow.\n")
    print("STEP 3 — Browser will show 'This site can't be reached' — that is NORMAL.")
    print("         Copy the FULL URL from the browser address bar.\n")

    redirect_response = input("STEP 4 — Paste the full URL here and press Enter:\n> ").strip()

    # Extract auth code
    parsed = urllib.parse.urlparse(redirect_response)
    query_params = urllib.parse.parse_qs(parsed.query)

    if "code" not in query_params:
        print("[ERROR] No 'code' found in the pasted URL. Make sure you copied the full URL.")
        return

    code = query_params["code"][0]

    # Exchange code for tokens (plain POST, no PKCE)
    token_data = urllib.parse.urlencode({
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }).encode()

    req = urllib.request.Request(token_uri, data=token_data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    with urllib.request.urlopen(req) as resp:
        token_response = json.loads(resp.read())

    if "error" in token_response:
        print(f"[ERROR] Token exchange failed: {token_response}")
        return

    # Save in google-auth compatible format
    token_json = {
        "token": token_response.get("access_token"),
        "refresh_token": token_response.get("refresh_token"),
        "token_uri": token_uri,
        "client_id": client_id,
        "client_secret": client_secret,
        "scopes": SCOPES,
    }
    TOKEN_FILE.write_text(json.dumps(token_json, indent=2))

    print(f"\n[OK] Token saved to: {TOKEN_FILE}")
    print("[OK] Gmail is now authorized!")
    print("\nNext step: uv run gmail_watcher.py --once")


if __name__ == "__main__":
    main()
