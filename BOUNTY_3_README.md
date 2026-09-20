# Destructive-command guard for Claude Code

A dependency-free Python `PreToolUse` hook for Bash. It denies the destructive patterns required by bounty #3, records blocked attempts, and otherwise stays silent so normal Bash use is unaffected.

## What it blocks

- recursive + forced `rm` (including `-rf`, `-fr`, and long flags)
- `DROP TABLE`
- `git push --force`, `--force-with-lease`, and `-f`
- `TRUNCATE`
- `DELETE FROM` statements that do not contain a `WHERE` clause

Blocked attempts are appended to `~/.claude/hooks/blocked.log` with an ISO-8601 UTC timestamp, project path, and attempted command.

## Install (2 commands)

```bash
mkdir -p ~/.claude/hooks && cp destructive_command_guard.py ~/.claude/hooks/ && chmod +x ~/.claude/hooks/destructive_command_guard.py
python3 install_hook.py
```

The installer safely merges this hook into `~/.claude/settings.json` without deleting unrelated settings or existing hooks. Restart Claude Code after installation.

## Test

```bash
python3 -m unittest -v test_destructive_command_guard.py
```

The hook reads Claude Code's JSON event from stdin. For a blocked Bash call it returns a `PreToolUse` `deny` decision with a human-readable reason; allowed commands produce no output.
