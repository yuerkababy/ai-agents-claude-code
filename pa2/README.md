# Localhost Port Scanner + Process Auditor

Scans open TCP ports on `127.0.0.1`, identifies the process that owns each one,
and flags suspicious port/process combinations for security review.

It only ever connects to `127.0.0.1`. It never scans external hosts.

## Requirements

- Python 3
- [`psutil`](https://pypi.org/project/psutil/) (the only external dependency)

```
pip install psutil
```

## Usage

```
python port_scanner.py [--start PORT] [--end PORT]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--start` | `1` | First port to scan (1-65535) |
| `--end` | `65535` | Last port to scan (1-65535) |

Examples:

```
python port_scanner.py                       # scan all ports
python port_scanner.py --start 1 --end 1024  # well-known ports only
```

Invalid values (out of range, non-numeric, or `--start` greater than `--end`)
print a clear error and exit.

### Administrator rights

Some process details (PID, name, or path) need elevated rights. Without them the
scanner does not crash: affected rows show `(access denied)` or `-`, and a
warning suggests re-running as administrator. For the fullest results, run from
an elevated terminal.

## Output

A summary table, one row per open port, followed by a count summary:

```
PORT   PID   PROCESS       PATH                              FLAG  REASON
-----  ----  ------------  --------------------------------  ----  ------
135    1504  svchost.exe   C:\Windows\System32\svchost.exe   OK
445    4     System        -                                 OK

Summary: 0 suspicious, 0 to review, 2 ok
```

### Flags

| Flag | Meaning |
|------|---------|
| `OK` | Nothing unusual found |
| `REVIEW` | Worth a look: non-standard install path, or the process could not be inspected |
| `SUSPICIOUS` | Likely problem, see the REASON column |

Checks that produce `SUSPICIOUS`:

- A port listed as "(none expected)" is open
- A listed port is owned by a process other than its expected owner
- A process name mimics a system process (e.g. `scvhost.exe`, `svchost32.exe`)
- The executable runs from a temp, appdata, or downloads folder
- A `svchost.exe` whose parent is not `services.exe`, or a lone instance

Ports marked "Varies" in the mappings file (e.g. 80, 443, 5000) are not checked
for owner, since any owner can be legitimate there.

Digital-signature checking is not implemented.

## Configuring the rules

Port-to-process rules are read from `expected-port-mappings.md` (a markdown
table in the same folder as `port_scanner.py`). Edit that table to change what
counts as expected. The file is only read, never written by the scanner.

If the file is missing or unreadable, the scan still runs with a warning; only
the path and process-name checks are applied.

## Tests

```
python -m unittest discover -s tests
```

## Files

| File | Purpose |
|------|---------|
| `port_scanner.py` | Scanner, process attribution, and flagging logic |
| `expected-port-mappings.md` | Reference mappings and suspicious indicators |
| `tests/` | Unit tests for flagging and process attribution |