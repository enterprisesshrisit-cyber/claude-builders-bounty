#!/usr/bin/env python3
"""Claude Code PreToolUse hook that blocks destructive Bash commands."""
from __future__ import annotations
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path.home() / ".claude" / "hooks" / "blocked.log"

RULES = (
    ("recursive forced deletion", re.compile(r"(?i)(?:^|[;&|()]\s*)rm\s+(?=(?:[^\n;&|]*\s)?)(?=[^\n;&|]*-(?:[^\s]*r[^\s]*f|[^\s]*f[^\s]*r)\b)|(?:^|[;&|()]\s*)rm\s+--recursive\s+--force\b|(?:^|[;&|()]\s*)rm\s+--force\s+--recursive\b")),
    ("DROP TABLE", re.compile(r"(?i)\bdrop\s+table\b")),
    ("forced git push", re.compile(r"(?i)\bgit\s+push\b[^\n;&|]*(?:--force(?:-with-lease|-if-includes)?\b|-f(?:\s|$))")),
    ("TRUNCATE", re.compile(r"(?i)\btruncate(?:\s+table)?\s+[\w\"\x60\[]")),
)

DELETE_RE = re.compile(r"(?is)\bdelete\s+from\b(?P<body>.*?)(?=;|$)")
WHERE_RE = re.compile(r"(?i)\bwhere\b")

def reason_for(command: str) -> str | None:
    for reason, pattern in RULES:
        if pattern.search(command):
            return reason
    for match in DELETE_RE.finditer(command):
        if not WHERE_RE.search(match.group("body")):
            return "DELETE FROM without a WHERE clause"
    return None

def log_block(command: str, cwd: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    safe_command = command.replace("\n", "\\n").replace("\r", "\\r")
    safe_cwd = cwd.replace("\n", "\\n").replace("\r", "\\r")
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(f"{stamp}\t{safe_cwd}\t{safe_command}\n")

def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError):
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    tool_input = payload.get("tool_input") or {}
    command = tool_input.get("command")
    if not isinstance(command, str):
        return 0
    reason = reason_for(command)
    if reason is None:
        return 0
    cwd = str(payload.get("cwd") or os.getcwd())
    log_block(command, cwd)
    message = f"Blocked destructive Bash command: {reason}. Rewrite the operation using a safer, scoped command."
    json.dump({"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":message}}, sys.stdout)
    sys.stdout.write("\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
