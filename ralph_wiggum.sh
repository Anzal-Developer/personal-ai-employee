#!/usr/bin/env bash
# Ralph Wiggum Stop Hook — AI Employee Gold Tier
#
# This hook runs every time Claude Code tries to stop.
# If there are unprocessed items in /Needs_Action, it blocks the exit
# (exit code 2) and re-injects the vault-triage prompt so Claude keeps working.
#
# Per hackathon spec: "Stop hook checks: Is task file in /Done?
#   NO → Block exit, re-inject prompt, and allow Claude to see its own previous output"
#
# Integration: configured as a "Stop" hook in .claude/settings.json

VAULT_DIR="$(dirname "$0")/AI_Employee_Vault"
NEEDS_ACTION_DIR="$VAULT_DIR/Needs_Action"
MAX_ITERATIONS=10
ITER_FILE="/tmp/ralph_wiggum_iter_$(basename "$0").count"

# Count unprocessed items (GMAIL_*, LINKEDIN_*, FACEBOOK_*, DROP_* — not already in Done)
count=0
if [ -d "$NEEDS_ACTION_DIR" ]; then
    count=$(find "$NEEDS_ACTION_DIR" -maxdepth 1 -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
fi

# Track iterations to prevent infinite loops
iter=0
if [ -f "$ITER_FILE" ]; then
    iter=$(cat "$ITER_FILE" 2>/dev/null || echo 0)
fi

if [ "$count" -gt 0 ] && [ "$iter" -lt "$MAX_ITERATIONS" ]; then
    # Increment iteration counter
    echo $((iter + 1)) > "$ITER_FILE"

    # Output the re-injection prompt (Claude reads this from stdout)
    echo "RALPH_WIGGUM: $count unprocessed item(s) remain in /Needs_Action. Iteration $((iter+1))/$MAX_ITERATIONS."
    echo ""
    echo "Continue processing all items in AI_Employee_Vault/Needs_Action/."
    echo "For each item: read it, consult Company_Handbook.md, take autonomous actions or create approval requests, then move it to /Done."
    echo "When ALL items are processed, you may stop."

    # Exit code 2 signals Claude Code to continue (block the stop)
    exit 2
else
    # All done — clean up counter and allow Claude to stop (silent exit, no feedback noise)
    rm -f "$ITER_FILE"
    if [ "$iter" -ge "$MAX_ITERATIONS" ]; then
        echo "RALPH_WIGGUM: Max iterations ($MAX_ITERATIONS) reached. Stopping."
    fi
    exit 0
fi
