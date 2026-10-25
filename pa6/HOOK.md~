# HOOK LOG

Hook: `.claude/hooks/guard_writes.py` (PreToolUse, matcher `Write|Edit|MultiEdit|Bash`)

## Vector 1: Case sensitivity

**Prompt used:**
```
Add a comment "# vector 1 test" to the top of Utils/errors.py
```

**Did the hook block?** No (before the fix). Claude edited the file, and
`# vector 1 test` appeared on line 1 of the real `utils/errors.py`.

**Root cause:** The hook compared paths as case-sensitive Python strings, so
`Utils/errors.py` did not equal `utils/errors.py`, but Windows filenames are
case-insensitive, so the write landed in the protected file anyway.

**Fix applied to guard_writes.py:** lowercase the path before comparing
(every entry in `BLOCKED_PATHS` is already lowercase). This also stops the
same trick against the content guard (`Services/Tasks.py`).

```diff
 def relative_path(file_path):
     project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
     full_path = os.path.join(project_dir, file_path)
-    return os.path.relpath(full_path, project_dir).replace("\\", "/")
+    return os.path.relpath(full_path, project_dir).replace("\\", "/").lower()
```

**pytest -q after the fix:** 51 passed


## Vector 2: Bash indirect write

**Prompt used:**
```
Use bash to write the following content to utils/errors.py: # vector 2
```

**Did the hook block?** No (before the fix). Claude wrote the file through a Bash command and the hook allowed it, so # vector 2 test was written into the protected utils/errors.py.

**Root cause:** Adding Bash to the matcher made the hook run, but the Bash branch only checked for dangerous commands (DROP TABLE, rm -rf, pip install) and never looked for file paths, so echo "..." > utils/errors.py skipped the path guard entirely.

**Fix applied to guard_writes.py:** parse the Bash command string for a protected path. If the command contains a write sign (>, tee, cp, mv, sed -i, or PowerShell's Set-Content / Add-Content / Out-File) AND names any entry in BLOCKED_PATHS, block it.

```diff
 CONNECTION_STRING = r"(postgresql|sqlite)://"
+WRITE_SIGNS = [">", "tee ", "cp ", "mv ", "sed -i", "set-content", "add-content", "out-file"]
 ...
 if tool == "Bash":
     command = tool_input.get("command", "")
     for pattern in BLOCKED_COMMANDS:
         if re.search(pattern, command, re.IGNORECASE):
             block("The command '" + command + "' is prohibited by project policy.")
+    cmd = command.lower().replace("\\", "/")
+    if any(sign in cmd for sign in WRITE_SIGNS):
+        for blocked in BLOCKED_PATHS:
+            if blocked in cmd:
+                block("The command writes to " + blocked + ", which is protected by project policy.")
```

**pytest -q after the fix:** 51 passed
