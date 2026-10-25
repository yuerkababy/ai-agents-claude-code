name: Localhost Port Scanner + Process Auditor

Scans open ports on 127.0.0.1, identifies the owning process for each, and flags suspicious port/process combinations for security review.

Stack: Python 3 (standard library + psutil)

## Commands
- Install: `pip install psutil`
- Test: `python -m unittest discover -s tests`
- Lint: `python -m py_compile port_scanner.py`
- Build/Run: `python port_scanner.py`

## Conventions
- Use Python 3
- Use the Python standard library wherever possible; `psutil` is the one approved external dependency for process/port inspection
- Handle invalid or missing input with clear error messages
- Handle permission errors gracefully (some process info requires admin rights) — degrade with a clear message instead of crashing
- Only scan 127.0.0.1 — never scan external hosts or live network targets
- Read flagging rules from `expected-port-mappings.md` rather than hardcoding them deep in scan logic, so the mapping stays easy to update
- Keep console output as a clean, readable summary table (port, PID, process name, path, risk flag/reason)

## Do Not
- Do not create, modify, or overwrite `expected-port-mappings.md`
- Do not scan or connect to any host other than 127.0.0.1
- Do not use unnecessary external libraries beyond `psutil`
- Do not remove or weaken error handling to "simplify" the code
