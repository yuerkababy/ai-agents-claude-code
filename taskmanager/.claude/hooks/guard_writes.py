#!/usr/bin/env python
"""PreToolUse hook: blocks writes to protected files and directories."""
import json, sys, os, re

BLOCKED_PATHS = [
    "utils/errors.py",
    "requirements.txt",
    "migrations/",
    ".env",
    ".claude/settings.json",
    ".claude/hooks/",
]
BLOCKED_COMMANDS = [
    r"\b(DROP|TRUNCATE)\s+TABLE\b",
    r"\brm\s+-(rf|fr)\b",
    r"\bpip\s+install\b",
]

CONTENT_GUARDED_FILE = "services/tasks.py"
CONNECTION_STRING = r"(postgresql|sqlite)://"
WRITE_SIGNS = [">", "tee ", "cp ", "mv ", "sed -i", "set-content", "add-content", "out-file"]

def block(message):
    """Stop the tool call and tell Claude why."""
    print("BLOCKED: " + message, file=sys.stderr)
    sys.exit(2)

def relative_path(file_path):
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    full_path = os.path.join(project_dir, file_path)
    return os.path.relpath(full_path, project_dir).replace("\\", "/").lower()

# ---- Read what Claude is about to do ----
data = json.load(sys.stdin)
tool = data.get("tool_name", "")
tool_input = data.get("tool_input", {})

# ---- Extension 1: Bash command guard ----
if tool == "Bash":
    command = tool_input.get("command", "")
    for pattern in BLOCKED_COMMANDS:
        if re.search(pattern, command, re.IGNORECASE):
            block("The command '" + command + "' is prohibited by project policy.")
    cmd = command.lower().replace("\\", "/")
    if any(sign in cmd for sign in WRITE_SIGNS):
        for blocked in BLOCKED_PATHS:
            if blocked in cmd:
                block("The command writes to " + blocked + ", which is protected by project policy.")


# ---- File write guards ----
if tool in ("Write", "Edit", "MultiEdit"):
    path = relative_path(tool_input.get("file_path", ""))
 
    # Drill 2: path guard
    for blocked in BLOCKED_PATHS:
        if path == blocked or (blocked.endswith("/") and path.startswith(blocked)):
            block(path + " is protected by project policy. "
                  "Update CLAUDE.md and remove the protection after team review.")
 
    # Extension 2: content guard
    if path == CONTENT_GUARDED_FILE:
        new_text = tool_input.get("content") or tool_input.get("new_string") or ""
        if re.search(CONNECTION_STRING, new_text, re.IGNORECASE):
            block("Do not hardcode a database connection string in " + path + ". "
                  "Connection strings must come from environment variables.")

# Nothing matched so allow it
sys.exit(0)
