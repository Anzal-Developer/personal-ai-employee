#!/usr/bin/env python3
"""
File System Watcher — AI Employee Bronze Tier
Monitors the Drop/ folder and routes files into AI_Employee_Vault/Needs_Action/
with a companion .md metadata file, then optionally triggers Claude Code.

Usage:
    python watcher.py

Requirements:
    pip install watchdog
"""

import os
import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from watchdog.observers.polling import PollingObserver as Observer
from watchdog.events import FileSystemEventHandler

# ── Config ────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent.resolve()
DROP_DIR = BASE_DIR / "Drop"
VAULT_DIR = BASE_DIR / "AI_Employee_Vault"
NEEDS_ACTION_DIR = VAULT_DIR / "Needs_Action"
LOGS_DIR = VAULT_DIR / "Logs"

# Set to True to automatically invoke Claude Code after each drop
AUTO_INVOKE_CLAUDE = False

# ── Helpers ───────────────────────────────────────────────────────────────────


def log_action(action: str, details: dict):
    """Append a JSONL log entry to today's log file."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"{today}.jsonl"
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        **details,
    }
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"[LOG] {entry}")


def detect_priority(filename: str) -> str:
    """Guess priority from filename keywords."""
    name_lower = filename.lower()
    if any(k in name_lower for k in ("urgent", "asap", "critical", "high")):
        return "high"
    if any(k in name_lower for k in ("invoice", "contract", "payment", "legal")):
        return "high"
    if any(k in name_lower for k in ("medium", "normal", "review")):
        return "medium"
    return "low"


def detect_type(filename: str) -> str:
    """Classify file by extension."""
    ext = Path(filename).suffix.lower()
    type_map = {
        ".txt": "text",
        ".md": "markdown",
        ".csv": "data",
        ".pdf": "pdf",
        ".docx": "document",
        ".doc": "document",
        ".xlsx": "spreadsheet",
        ".xls": "spreadsheet",
        ".png": "image",
        ".jpg": "image",
        ".jpeg": "image",
    }
    return type_map.get(ext, "unknown")


def create_metadata_file(src_path: Path, dest_path: Path, timestamp: str):
    """Write a companion .md metadata file for the dropped file."""
    filename = src_path.name
    size_bytes = src_path.stat().st_size
    priority = detect_priority(filename)
    file_type = detect_type(filename)

    meta_path = Path(str(dest_path) + ".md")
    content = f"""---
type: file_drop
original_name: {filename}
dropped_at: {timestamp}
size_bytes: {size_bytes}
file_type: {file_type}
priority: {priority}
status: pending
---

# File Drop: {filename}

A file has been dropped and is awaiting processing by the AI Employee.

## File Details

| Field | Value |
|-------|-------|
| Original Name | `{filename}` |
| Size | {size_bytes:,} bytes |
| Type | {file_type} |
| Priority | {priority} |
| Dropped At | {timestamp} |

## Instructions for AI Employee

1. Read `Company_Handbook.md` to determine the correct action.
2. If the file type is safe (`.txt`, `.md`, `.csv`): summarize and move to `/Done`.
3. If the file type requires approval (`.pdf`, `.docx`, invoice/contract): create an approval request in `/Pending_Approval`.
4. Log the action to `Logs/{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl`.
5. Update `Dashboard.md` after processing.
"""
    meta_path.write_text(content, encoding="utf-8")
    return meta_path


def process_drop(src_path: Path):
    """Handle a newly detected file in the Drop folder."""
    # Skip hidden files, temp files, and metadata files
    if src_path.name.startswith(".") or src_path.suffix == ".tmp":
        return
    if not src_path.is_file():
        return

    # Brief pause to ensure the file is fully written
    time.sleep(0.5)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest_name = f"DROP_{timestamp}_{src_path.name}"
    dest_path = NEEDS_ACTION_DIR / dest_name

    try:
        shutil.copy2(src_path, dest_path)
        meta_path = create_metadata_file(src_path, dest_path, timestamp)

        log_action(
            "file_dropped",
            {
                "original": src_path.name,
                "dest": dest_name,
                "meta": meta_path.name,
                "priority": detect_priority(src_path.name),
                "type": detect_type(src_path.name),
            },
        )

        print(f"[WATCHER] Processed drop: {src_path.name} → {dest_name}")
        print(f"[WATCHER] Metadata:        {meta_path.name}")

        # Remove from Drop folder after successful copy
        src_path.unlink()

        if AUTO_INVOKE_CLAUDE:
            invoke_claude()

    except Exception as e:
        print(f"[ERROR] Failed to process {src_path.name}: {e}")
        log_action("error", {"file": src_path.name, "error": str(e)})


def invoke_claude():
    """Trigger Claude Code to process the new drop."""
    print("[WATCHER] Invoking Claude Code for vault triage…")
    try:
        subprocess.Popen(
            ["claude", "-p", "Run the vault-triage skill to process all pending items."],
            cwd=str(BASE_DIR),
        )
    except FileNotFoundError:
        print("[WATCHER] Claude Code not found in PATH. Skipping auto-invoke.")


# ── Watchdog Handler ──────────────────────────────────────────────────────────


class DropHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            process_drop(Path(event.src_path))

    def on_moved(self, event):
        # Handle files moved into the Drop folder
        if not event.is_directory:
            dest = Path(event.dest_path)
            if dest.parent == DROP_DIR:
                process_drop(dest)


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    # Ensure required directories exist
    DROP_DIR.mkdir(parents=True, exist_ok=True)
    NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  AI Employee — File System Watcher")
    print("=" * 60)
    print(f"  Watching:    {DROP_DIR}")
    print(f"  Vault:       {VAULT_DIR}")
    print(f"  Auto-Claude: {AUTO_INVOKE_CLAUDE}")
    print("=" * 60)
    print("  Drop files into the Drop/ folder to trigger the AI Employee.")
    print("  Press Ctrl+C to stop.")
    print()

    log_action("watcher_started", {"drop_dir": str(DROP_DIR), "vault_dir": str(VAULT_DIR)})

    observer = Observer()
    observer.schedule(DropHandler(), str(DROP_DIR), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        log_action("watcher_stopped", {"reason": "keyboard_interrupt"})
        print("\n[WATCHER] Stopped.")

    observer.join()


if __name__ == "__main__":
    main()
