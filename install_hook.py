#!/usr/bin/env python3
import json
from pathlib import Path

settings = Path.home() / ".claude" / "settings.json"
settings.parent.mkdir(parents=True, exist_ok=True)
try:
    data = json.loads(settings.read_text(encoding="utf-8")) if settings.exists() else {}
except json.JSONDecodeError as exc:
    raise SystemExit(f"Refusing to overwrite invalid {settings}: {exc}")

entry = {"matcher":"Bash","hooks":[{"type":"command","command":"python3 ~/.claude/hooks/destructive_command_guard.py"}]}
hooks = data.setdefault("hooks", {}).setdefault("PreToolUse", [])
if entry not in hooks:
    hooks.append(entry)
settings.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print(f"Installed PreToolUse hook in {settings}")
