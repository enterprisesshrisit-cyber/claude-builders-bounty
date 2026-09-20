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

RM_COMMAND_RE = re.compile(
    r"(?ix)(?:^|[;&|()]\s*)"
    r"(?:(?:sudo|command)\s+)*"
    r"(?:\S*/)?rm\b(?P<args>[^\n;&|]*)"
)
GIT_PUSH_RE = re.compile(
    r"(?ix)(?:^|[;&|()]\s*)"
    r"(?:(?:sudo|command)\s+)*"
    r"(?:\S*/)?git\s+push\b(?P<args>[^\n;&|]*)"
)
DB_CLIENT_RE = re.compile(
    r"(?ix)(?:^|[;&|()]\s*)"
    r"(?:(?:sudo|command)\s+)*"
    r"(?:\S*/)?(?:psql|mysql|mariadb|sqlite3|duckdb)\b"
)
SQL_START_RE = re.compile(
    r"(?is)^\s*(?:drop\s+table\b|truncate(?:\s+table)?\b|delete\s+from\b)"
)
DROP_TABLE_RE = re.compile(r"(?i)\bdrop\s+table\b")
TRUNCATE_RE = re.compile(r"(?i)\btruncate(?:\s+table)?\s+[\w\"\x60\[]")
DELETE_RE = re.compile(
    r"(?is)\bdelete\s+from\b(?P<body>.*?)(?=;|&&|\|\||\|(?=\s)|$)"
)
WHERE_RE = re.compile(r"(?i)\bwhere\b")
SQL_COMMENT_RE = re.compile(r"/\*.*?\*/|--[^\r\n]*", re.S | re.M)


def _option_tokens(args: str) -> list[str]:
    """Return option-like shell tokens up to -- for flag inspection."""
    tokens = re.findall(r'''(?:"[^"]*"|'[^']*'|\S+)''', args)
    result: list[str] = []
    for token in tokens:
        if token == "--":
            break
        result.append(token)
    return result


def _has_recursive_forced_rm(command: str) -> bool:
    for match in RM_COMMAND_RE.finditer(command):
        recursive = False
        force = False
        for token in _option_tokens(match.group("args")):
            if token == "--recursive":
                recursive = True
            elif token == "--force":
                force = True
            elif token.startswith("-") and not token.startswith("--"):
                flags = token[1:]
                recursive = recursive or "r" in flags or "R" in flags
                force = force or "f" in flags
        if recursive and force:
            return True
    return False


def _has_forced_git_push(command: str) -> bool:
    for match in GIT_PUSH_RE.finditer(command):
        for token in _option_tokens(match.group("args")):
            if token in {"--force", "--force-with-lease", "--force-if-includes", "-f"}:
                return True
            if token.startswith("--force-with-lease="):
                return True
    return False


def _is_sql_context(command: str) -> bool:
    # Raw SQL at the start is blocked, as is destructive SQL passed to a
    # common database CLI. Harmless mentions such as echo "DROP TABLE ..."
    # remain normal Bash commands.
    return bool(SQL_START_RE.search(command) or DB_CLIENT_RE.search(command))


def _strip_sql_comments(text: str) -> str:
    return SQL_COMMENT_RE.sub(" ", text)


def reason_for(command: str) -> str | None:
    if _has_recursive_forced_rm(command):
        return "recursive forced deletion"

    if _has_forced_git_push(command):
        return "forced git push"

    if _is_sql_context(command):
        if DROP_TABLE_RE.search(command):
            return "DROP TABLE"
        if TRUNCATE_RE.search(command):
            return "TRUNCATE"
        for match in DELETE_RE.finditer(command):
            body = _strip_sql_comments(match.group("body"))
            if not WHERE_RE.search(body):
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

    message = (
        f"Blocked destructive Bash command: {reason}. "
        "Rewrite the operation using a safer, scoped command."
    )
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": message,
            }
        },
        sys.stdout,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
