# SPEC: Hardening `port_scanner.py`

Work is done in four phases, in this order: **docstrings, then validation, then
tests, then error handling**. Each phase ships with its own tests: phase 3 builds
the suite for phases 1–2, and phase 4 adds tests for every new error path.

---

## 0. Context and decisions

`port_scanner.py` connect-scans TCP ports on localhost. It attributes each open
port to a process with psutil and flags each port OK, REVIEW or SUSPICIOUS
against `expected-port-mappings.md` plus heuristics for path, typosquatting and
svchost parentage. The code already has Google-style docstrings, `_check_*`
validators and some error handling. There are no tests.

| Topic | Decision |
|---|---|
| Docstrings / validation | Audit the existing code and fill gaps; no rewrite. Keep the Google docstring style. |
| Platform | Windows only. Other OSes may run but aren't supported. Tests must still pass on non-Windows because Windows-specific checks are mocked or skipped. |
| API surface | CLI **and** importable library. The public functions' signatures, return shapes and exceptions are a contract and get tested. |
| Phase ordering | Keep the order. Tests are written per phase (phase 4 extends the suite). |
| Mappings-file validation | Skip bad rows and emit a warning for each one; valid rows are still used. |
| New CLI options | `--timeout`, `--workers`, `--debug`, all validated. |
| Scan method | Keep the connect scan. Document the Windows closed-port cost. |
| Multiple PIDs per port | Record all of them, one output row per (port, PID). |
| IPv6 | Connect-scan both `127.0.0.1` and `::1` by default and merge the results. |
| Exit codes | 0 OK, 1 runtime error, 2 bad args, 3 REVIEW present, 4 SUSPICIOUS present, 130 Ctrl+C. |
| Missing/unusable mappings | Exit code is at least 3. |
| Ctrl+C | Abort, print no table, exit 130. |
| Graceful failures | Unexpected psutil errors degrade to REVIEW rows. Ctrl+C is handled. |
| Unexpected exceptions | One-line message on stderr and exit 1; `--debug` shows the traceback. |
| Typosquat heuristic | Tune it and pin the behavior with table-driven tests. |
| `%LOCALAPPDATA%\Programs` | Downgrade from SUSPICIOUS to REVIEW. |
| Authenticode / "System on 445 with sharing off" | Out of scope. Documented as not checked. |
| Tests | pytest in `tests/`: mostly mocked, plus a few real-socket tests. Coverage of at least 90% line+branch. |

### Out of scope (documented, not built)
- Authenticode signature verification of executables.
- The "System on 445 while file/printer sharing is disabled" check.
- UDP scanning (rows with a UDP-only protocol are ignored, as today).
- Filtering listeners by bound IP (e.g. excluding a listener bound only to a LAN
  IP on the same port number). This is listed as a known limitation.
- Console-encoding / broken-pipe hardening. Such failures fall through to the
  generic crash handler (exit 1, see §4.4) and are listed as a known limitation.
- A psutil-based scan mode.

---

## 1. Phase 1: Docstring audit

Goal: every docstring is accurate for the **final** behavior of its phase. When
phases 2 and 4 change behavior they update the docstrings they affect, and this
phase fixes what is inaccurate or missing today.

### 1.1 Module docstring additions
- **Platform:** Windows only. Path heuristics use `SystemRoot`, `ProgramFiles`,
  `ProgramFiles(x86)`, `ProgramW6432` and `LOCALAPPDATA`.
- **Addresses scanned:** `127.0.0.1` and `::1`. If IPv6 is unavailable, only
  IPv4 is scanned and a warning is printed.
- **Performance note:** on Windows, a connect to a *closed* localhost port does
  not fail immediately, because the stack retries the SYN after an RST. Closed
  ports therefore usually cost the full `--timeout`. A full scan is about
  `65535 × 2 families × timeout / workers` seconds; with the defaults
  (0.3 s, 200 workers) that is roughly 3 minutes.
- **Exit codes** table (see §4.3).
- **Not checked:** Authenticode signatures, and "System on 445 while sharing is
  disabled". The mappings doc lists both, but they are not implemented.
- **Known limitations:** listeners are attributed by port number regardless of
  bound IP; console-encoding issues are not handled specially.
- Update `Attributes:` to cover the new constants (`HOSTS`, timeout/worker
  bounds, exit-code constants, `LOCAL_PROGRAMS_MARKER`, etc.).

### 1.2 Per-function fixes (current inaccuracies and gaps)
- `describe_process`: say that `psutil.ZombieProcess` is a subclass of
  `NoSuchProcess`, so a zombie's `name()` failure yields the "exited" status.
  Update for the new `ProcessInfo` return type (§2.4).
- `format_table`: the docstring only lists `ValueError`, but a non-`str` name or
  path currently raises an undocumented `TypeError` from `len()`. After §2.6
  this is an explicit `TypeError`; document it.
- `build_port_pid_map`: the "first PID seen is kept" text changes to "all
  PIDs" (§2.3).
- `load_expected_mappings`: the return type changes (§2.1).
- `flag_process`: document the `%LOCALAPPDATA%\Programs` rule, the tuned
  typosquat rule, and that the inspectability check uses `ProcessInfo.status`
  rather than name sentinels.
- Private helpers keep their docstrings. Every `Raises:` section must list
  exactly what the function can raise, and phase 3 tests verify each entry.

**Acceptance:** each public function's docstring states Args, Returns and
Raises that match the behavior. Phase 3 has a test for every `Raises:` entry.

---

## 2. Phase 2: Validation (and the correctness fixes it uncovers)

### 2.1 Mappings file (`load_expected_mappings`)
New return shape: `(mappings, messages)`, where `messages` is a
`list[str]` (possibly empty). *This is a deliberate API change.*
- A **fatal** condition is a file that is missing, unreadable, undecodable, or
  has no valid rows. It returns `({}, [msg])`.
- For **row-level** problems, the row is skipped and a warning is appended. The
  warning includes the 1-based line number and the offending text.
  - The port cell must match `^[0-9]+$` (ASCII only). Today `str.isdigit()`
    accepts `"²"` and `"٣"`, and then `int()` raises `ValueError` and crashes.
  - The port must be within `MIN_PORT`–`MAX_PORT`. `0` and `99999` are rejected.
  - **Duplicate port:** the first occurrence wins. Later rows are skipped with
    a warning. (Today the last one silently wins.)
  - If the expected-process cell yields no names and isn't
    "Varies"/"(none expected)" (e.g. an empty cell), the row is still used as
    "not checked" (`None`) and a warning is emitted.
  - Tables with fewer than 4 cells, header/separator rows and non-TCP rows are
    skipped silently. This is not an error.
- Callers can tell "file unusable" (`mappings == {}` and messages non-empty)
  apart from "some rows bad" (`mappings` non-empty and messages non-empty).
- **Test oracle:** the shipped `expected-port-mappings.md` parses into exactly
  these 13 ports with **no** messages:
  21, 22, 23, 25, 53, 80, 135, 139, 443, 445, 3389, 5000, 5357.

### 2.2 CLI (`parse_args`)
| Flag | Type | Default | Valid range | Notes |
|---|---|---|---|---|
| `--start` | int | 1 | 1–65535 | existing |
| `--end` | int | 65535 | 1–65535, ≥ start | existing |
| `--timeout` | float | 0.3 | 0.05–10.0 | must reject `nan` and `inf` |
| `--workers` | int | 200 | 1–1000 | |
| `--debug` | flag | off | — | enables tracebacks (§4.4) |

- `float("nan")` and `float("inf")` parse successfully. A chained comparison
  `lo <= v <= hi` happens to reject NaN, but the check must use
  `math.isfinite()` explicitly so the intent is visible. Test both.
- `int()` accepts `"+80"`, `" 80 "` and `"8_0"`. These are **accepted** as
  harmless; the behavior is pinned by a test so it doesn't change by accident.
- All range errors go through `parser.error(...)` (exit 2, usage on stderr).

### 2.3 Scanning and listener map
- **Localhost-only invariant:** `HOSTS = ("127.0.0.1", "::1")`.
  `is_port_open(port, host=HOSTS[0], timeout=CONNECT_TIMEOUT)` raises
  `ValueError` if `host not in HOSTS`. This is a safety property: the
  function must never be usable against a non-local address. Test it
  explicitly, e.g. that `"192.168.1.1"`, `"localhost"` and `"0.0.0.0"` are
  rejected.
- The socket family is chosen from the host (`AF_INET` / `AF_INET6`).
- `timeout` is validated as a finite float in the CLI range, and `workers` as
  an int in the CLI range. `bool` is rejected for both (consistent with
  `_check_port`).
- `scan_ports(start, end, *, timeout=..., workers=..., hosts=HOSTS)`
  returns `list[tuple[int, frozenset[str]]]`: `(port, families)` sorted by
  port, where `families ⊆ {"v4", "v6"}` and is non-empty.
  - IPv6 availability is probed once up front (create an `AF_INET6` socket). If
    that fails, scan v4 only and surface a warning ("IPv6 unavailable; ::1 not
    scanned"). `scan_ports` returns warnings alongside results, or exposes them
    via a small result object; the implementer chooses, but the shape must be
    documented and tested.
- `build_port_pid_map()` returns `dict[int, list[int]]`. It maps each LISTEN
  port to a **sorted, de-duplicated** list of PIDs across all local addresses
  (v4 and v6). Rows with `pid is None` still trigger the existing warning.
- `attribute_ports(open_ports)` takes the `(port, families)` pairs and yields
  **one row per (port, PID)**. A port with no known PID yields one row with
  `pid=None`.

### 2.4 Replace sentinel-string inspectability (security fix)
`flag_process` currently decides inspectability with
`name.startswith("(") or name == "unknown"`. A real executable named
`(evil).exe` or `unknown.exe` would therefore skip the owner, typosquat and
path checks and be downgraded to REVIEW, which makes it an easy way to dodge
detection.
- `describe_process(pid)` returns a `ProcessInfo` namedtuple
  `(name, path, status)`, where `status ∈ {"ok", "unknown", "exited",
  "denied", "error"}`. Display strings (`"(exited)"`, `"(access denied)"`,
  `"unknown"`) stay the same for the table.
- `flag_process` takes the status (e.g. `flag_process(port, pid, info,
  mappings)` or an added `status` argument; implementer's choice, but it must
  be documented). Inspectability is `status == "ok"`.
- Test: a process whose real name is `"(evil).exe"` on port 445 is flagged
  SUSPICIOUS, not REVIEW.

### 2.5 Path heuristic fixes
- Add `ProgramW6432` to `_standard_dirs()`. Under 32-bit Python on 64-bit
  Windows, `ProgramFiles` resolves to `C:\Program Files (x86)`, so every 64-bit
  app in `C:\Program Files` is currently wrongly flagged REVIEW.
- **`%LOCALAPPDATA%\Programs\`** (from the `LOCALAPPDATA` env var, lower-cased,
  trailing backslash) → **REVIEW** "user-level install
  (%LOCALAPPDATA%\Programs)". This check runs *before* the suspicious-marker
  check. Everything else under `\appdata\`, `\temp\` or `\downloads\` stays
  SUSPICIOUS. `C:\Windows\Temp\` stays SUSPICIOUS even though it is under
  `SystemRoot`, and that is intentional.
- If `LOCALAPPDATA` is unset, the exception doesn't apply and the path is
  SUSPICIOUS.

### 2.6 Remaining input validation
- `format_table`: beyond the existing shape check, validate each cell. `port` is
  int, `pid` is int or None, the other four are `str`, and `families` is a str
  if a column is added. Wrong types raise `TypeError` naming the row index and
  field.
- The table gains an **ADDR** column (`v4`, `v6`, `v4+v6`) after PORT. The row
  tuple becomes `(port, addr, pid, name, path, flag, reason)`.
- `flag_process`: validate that `mappings` keys are ints and values are
  2-tuples. A shallow check is enough; raise `TypeError` otherwise.
- `attribute_ports`: explicitly reject `str`/`bytes` input. Iterating `"80"`
  gives characters and currently produces a confusing error.

### 2.7 Typosquat heuristic tuning
Current: `difflib.get_close_matches(norm_name, known, cutoff=0.8)`.
Required changes:
1. **Normalize before comparing:** map leetspeak `0→o, 1→l, 3→e, 5→s`, and
   strip a trailing `32`/`64` or other digit run. If the normalized name
   *equals* a known name but the raw name didn't, flag SUSPICIOUS
   ("name mimics a system process").
2. **Length floor:** fuzzy matching only applies to known names of length ≥ 5.
   Short names (`dwm`, `smss`, `lsass` is 5 so it's included) match only through
   rule 1, which avoids false positives such as `dwmx` and `sms`.
3. Precompute the `known` set once per scan rather than per row. This is an
   optional refactor, but it must not change behavior.

**Acceptance table** (added as a parametrized test; the implementer tunes the
rules until every row passes):

| Name | Expected |
|---|---|
| `scvhost.exe`, `svch0st.exe`, `svchost32.exe`, `svchost64.exe`, `1sass.exe`, `lsasss.exe`, `csrsss.exe`, `expl0rer.exe`, `winl0gon.exe`, `spoo1sv.exe` | flagged "mimics a system process" |
| `svchost.exe`, `System`, `lsass.exe`, `services.exe`, `spoolsv.exe`, `dwm.exe`, `sshd.exe`, `chrome.exe`, `msedge.exe`, `python.exe`, `node.exe`, `Code.exe`, `sihost.exe`, `SearchHost.exe`, `RuntimeBroker.exe` | not flagged by this rule |

If a "not flagged" name cannot be cleared without losing a "flagged" one, stop
and raise it with the user. Don't silently drop the row.

---

## 3. Phase 3: Tests

### 3.1 Tooling and layout
- pytest and pytest-cov, listed in `requirements-dev.txt` (with `psutil` in
  `requirements.txt`).
- Command:
  `python -m pytest --cov=port_scanner --cov-branch --cov-fail-under=90`
- Configuration goes in `pytest.ini` (or `pyproject.toml`), with markers
  `integration` and `windows`.
- Layout:
  ```
  tests/
    conftest.py          # fakes: FakeConn, FakeProcess, env + mappings fixtures
    test_validation.py   # _check_*, parse_args, every documented Raises
    test_mappings.py     # _parse_expected, load_expected_mappings (§2.1)
    test_attribution.py  # build_port_pid_map, describe_process, attribute_ports
    test_flagging.py     # flag_process, typosquat table, path rules, svchost
    test_format.py       # format_table
    test_cli.py          # main(): output, stderr warnings, exit codes
    test_scan_integration.py  # real sockets (marker: integration)
  ```

### 3.2 Mocking strategy
- psutil is mocked with `monkeypatch` on `port_scanner.psutil.net_connections`,
  `port_scanner.psutil.Process` and `port_scanner.psutil.process_iter`.
- `FakeConn(status, laddr, pid)`, where `laddr` has `.ip` and `.port`.
- `FakeProcess(pid, name, exe, parent)` can be configured to raise
  `NoSuchProcess`, `AccessDenied` or `ZombieProcess` from `name()`, `exe()`
  or `parent()`.
- Environment variables (`SystemRoot`, `ProgramFiles`, `ProgramFiles(x86)`,
  `ProgramW6432`, `LOCALAPPDATA`) are set with `monkeypatch.setenv` or
  `delenv`, so path tests are deterministic on any OS. Tests use Windows-style
  paths and mock `os.path.isabs` where needed on non-Windows (or
  `ntpath.isabs` is used in the code; the implementer's choice, documented).
- Mappings files are written to `tmp_path`. A single test reads the real
  `expected-port-mappings.md` (the 13-port oracle, §2.1).

### 3.3 Required coverage (behavior checklist)
- Every `Raises:` entry in every docstring, including the `bool` rejection in
  `_check_port` / `_check_pid`.
- `parse_args`: defaults; each bound ± 1; `start > end`; `nan`/`inf`/`0.04`/
  `10.01` for timeout; `0`/`1001` for workers; a single-string `argv`
  raising `TypeError`; the `+80`/`8_0` acceptance.
- Mappings: each rule in §2.1, including `²`, `0`, `99999`, duplicates, empty
  cell, missing file, directory path, undecodable bytes, and a file with no
  table.
- Listener map: multiple PIDs on one port (sorted, de-duplicated), v4 and v6
  listeners on the same port, a `pid=None` warning, `AccessDenied` from
  `net_connections`.
- `describe_process`: each `status` value.
- Flagging, with one test per reason string:
  - owner mismatch
  - no-expected-owner
  - "Varies" is not checked
  - typosquat table (§2.7)
  - svchost with the wrong parent, `None` parent, a lone instance, and
    `AccessDenied` (returns None)
  - Temp/AppData/Downloads paths → SUSPICIOUS
  - `LOCALAPPDATA\Programs` → REVIEW
  - non-standard path → REVIEW
  - `ProgramW6432` → OK
  - non-inspectable → REVIEW
  - the `(evil).exe` bypass (§2.4)
  - reason joining and severity ordering
- `format_table`: empty rows (header only), width calculation, `pid=None` shown
  as `-`, ADDR column, each type error.
- `main()`, with `scan_ports` / `attribute_ports` mocked: each exit code
  (0, 3, 4); a missing mappings file forcing ≥ 3; the no-open-ports path
  (exit 0); warnings on stderr and the table on stdout; summary counts by
  **port** using its worst flag across PIDs.

### 3.4 Real-socket integration tests (`@pytest.mark.integration`)
These don't need admin and use only ephemeral ports.
- Bind a listener on `("127.0.0.1", 0)`. `is_port_open` is True; after close it
  is False (use `timeout=0.05` to keep it fast despite the Windows RST retry).
- Same for `("::1", 0)`. Skip if `socket.has_ipv6` is False or the bind fails.
- `scan_ports(p-2, p+2, timeout=0.05, workers=8)` finds the bound port with the
  correct families.
- End-to-end: `main(["--start", str(p), "--end", str(p), "--timeout", "0.05"])`
  prints a row for `p`. Only the port is asserted; PID and name are checked
  leniently, because attribution can vary by privilege.
- The full suite must finish in < 30 s on Windows.

---

## 4. Phase 4: Error handling

Each item below comes with tests added in this phase.

### 4.1 psutil failures degrade instead of crashing
- `build_port_pid_map`: catch `psutil.Error` and `OSError` (in addition to the
  current `AccessDenied`/`PermissionError`). The result is an empty map plus a
  warning: "Could not read connection table: <exc>".
- `describe_process`: any other `psutil.Error` or `OSError` from `Process()`,
  `name()` or `exe()` gives `status="error"` with name `"(error)"`, which
  flags as REVIEW "process could not be inspected".
- `_svchost_parent_issue`: widen the handler to `psutil.Error` and `OSError`
  and return None ("cannot tell; do not guess"), as today.
- A single bad process must never abort the scan. Test this by making one
  `FakeProcess` raise `RuntimeError`-like psutil errors while the other rows
  still print.

### 4.2 Ctrl+C
- `main` catches `KeyboardInterrupt` anywhere (scan, attribution or
  flagging). It prints `Scan interrupted.` to stderr, prints **no table**, and
  returns 130.
- `scan_ports` must not use `with ThreadPoolExecutor(...)`, because its exit
  calls `shutdown(wait=True)`, which drains every queued port (possibly minutes
  of work) before the interrupt takes effect. Instead:
  - Submit work in bounded chunks (e.g. `workers × 4` futures in flight) rather
    than all ~131k futures at once. This keeps memory flat and cancellation
    cheap.
  - The main thread waits with `concurrent.futures.wait(..., timeout=0.2)` in a
    loop, **not** a blocking `result()`. On Windows, Ctrl+C may not interrupt a
    lock wait that has no timeout.
  - On interrupt: `executor.shutdown(wait=False, cancel_futures=True)`, then
    re-raise.
  - Worst-case exit latency is about one `--timeout` (in-flight connects
    finish), and the tests must verify it stays under 1 s with a 0.05 s timeout.
- Test: mock `is_port_open` to block and raise `KeyboardInterrupt` in the main
  thread (e.g. patch `concurrent.futures.wait` to raise on its second call).
  Assert exit code 130, nothing printed to stdout after the "Scanning…" line,
  and that pending futures were cancelled.

### 4.3 Exit codes
| Code | Meaning |
|---|---|
| 0 | Scan completed and every row is OK, or no open ports were found |
| 1 | Runtime error (unexpected exception, §4.4) |
| 2 | Invalid arguments (argparse) |
| 3 | At least one REVIEW and no SUSPICIOUS, **or** the mappings file is unusable (§2.1 fatal) |
| 4 | At least one SUSPICIOUS |
| 130 | Interrupted (Ctrl+C) |

- These are defined as module constants (`EXIT_OK`, `EXIT_ERROR`, …).
- Precedence: 130 > 1 > 4 > 3 > 0.
- Row-level mappings warnings (bad rows skipped) do **not** change the exit
  code by themselves; they are printed to stderr.
- A missing or unusable mappings file with zero open ports still exits 0,
  because nothing was left unchecked. Pin this with a test.

### 4.4 Unexpected exceptions
- `main` wraps its body. Any exception that isn't `KeyboardInterrupt` or
  `SystemExit` prints `Error: <ExceptionType>: <message>` (one line) to stderr
  and returns 1.
- With `--debug`, the full traceback is also printed (`traceback.print_exc()`),
  and the exit code is still 1.
- Argument errors happen before `--debug` is known, and they keep the argparse
  behavior (exit 2).
- `TypeError` for a single-string `argv` (a programmer error in library use)
  propagates unchanged when `main()` is called as a library. The generic
  handler applies only inside the scan/report body.
- The `ImportError` for a missing psutil keeps its current `sys.exit(message)`
  behavior (exit 1). Exclude it from coverage with `# pragma: no cover`.

### 4.5 Output streams
- stdout: the "Scanning…" line, the table and the summary.
- stderr: warnings (permissions, IPv6 unavailable, mappings file/rows),
  interrupt and error messages.
- Warnings print after the summary (the current behavior), each prefixed with
  `Warning: `.

---

## 5. Definition of done
- [ ] All four phases have been implemented in order, each with its tests.
- [ ] `python -m pytest --cov=port_scanner --cov-branch --cov-fail-under=90`
      passes on Windows, and passes on Linux except for `windows`-marked tests.
- [ ] Every docstring's Args/Returns/Raises matches the behavior, with each
      Raises entry tested.
- [ ] The shipped mappings file parses into the 13-port oracle with no warnings.
- [ ] The typosquat acceptance table passes in full.
- [ ] Ctrl+C during a full default scan exits 130 within about 1 s and prints
      no table.
- [ ] The localhost-only invariant is enforced in code and tested.
- [ ] Out-of-scope heuristics and known limitations are listed in the module
      docstring.
