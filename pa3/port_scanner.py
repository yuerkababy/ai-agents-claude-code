"""Localhost port scanner + process attribution.

Scans TCP ports on 127.0.0.1 only, then uses psutil to identify the process
that owns each open port and prints a summary table. Each port is flagged
OK, REVIEW or SUSPICIOUS by comparing its owner against the expected owners
listed in ``expected-port-mappings.md`` and by applying install-path,
typosquat and svchost.exe parentage heuristics.

The mappings file is only ever read, never written.

Example:
    Scan every port, or a narrower range::

        $ python port_scanner.py
        $ python port_scanner.py --start 1 --end 1024

Attributes:
    HOST (str): The only address ever scanned (``127.0.0.1``).
    MIN_PORT (int): Lowest valid TCP port number.
    MAX_PORT (int): Highest valid TCP port number.
    CONNECT_TIMEOUT (float): Per-port connect timeout, in seconds.
    MAX_WORKERS (int): Number of threads used to scan ports concurrently.
    MAPPINGS_FILE (str): Path to the expected port -> process mappings file,
        next to this script.
    OK (str): Flag for a port with no findings.
    REVIEW (str): Flag for a port that should be checked by hand.
    SUSPICIOUS (str): Flag for a port that matches a known-suspicious rule.
    NO_EXPECTED_OWNER (frozenset): Marker for a port listed as
        "(none expected)" in the mappings file.
    BASE_SYSTEM_PROCESSES (frozenset): Well-known Windows process names used
        for typosquat detection.
    SUSPICIOUS_PATH_MARKERS (tuple): Lower-case path fragments that indicate
        an executable running from a user-writable location.
"""
import argparse
import difflib
import os
import re
import socket
import sys
from concurrent.futures import ThreadPoolExecutor

try:
    import psutil
except ImportError:
    sys.exit("Error: psutil is required. Install it with: pip install psutil")

HOST = "127.0.0.1"  # Only ever scan localhost.
MIN_PORT, MAX_PORT = 1, 65535
CONNECT_TIMEOUT = 0.3
MAX_WORKERS = 200
MAPPINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "expected-port-mappings.md")


def _check_port(value, name="port"):
    """Validate a TCP port number.

    Args:
        value: The value to check.
        name (str): Argument name used in error messages.

    Raises:
        TypeError: If ``value`` is not an int (bools are rejected).
        ValueError: If ``value`` is outside ``MIN_PORT``-``MAX_PORT``.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int, got {type(value).__name__}")
    if not MIN_PORT <= value <= MAX_PORT:
        raise ValueError(f"{name} must be between {MIN_PORT} and {MAX_PORT} "
                         f"(got {value})")


def _check_pid(value):
    """Validate a process ID, allowing None for "unknown".

    Args:
        value: The value to check.

    Raises:
        TypeError: If ``value`` is neither None nor an int (bools are
            rejected).
        ValueError: If ``value`` is negative.
    """
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"pid must be an int or None, got {type(value).__name__}")
    if value < 0:
        raise ValueError(f"pid must not be negative (got {value})")


def _check_str(value, name):
    """Validate that an argument is a string.

    Args:
        value: The value to check.
        name (str): Argument name used in error messages.

    Raises:
        TypeError: If ``value`` is not a str.
    """
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str, got {type(value).__name__}")


def parse_args(argv=None):
    """Parse and check the command-line arguments.

    Args:
        argv (list[str] | None): Arguments to parse. If None, ``sys.argv[1:]``
            is used.

    Returns:
        argparse.Namespace: Parsed arguments with integer ``start`` and
        ``end`` attributes, where
        ``MIN_PORT <= start <= end <= MAX_PORT``.

    Raises:
        TypeError: If ``argv`` is a single string rather than a list of
            strings (argparse would otherwise split it into characters).
        SystemExit: If an argument is not an integer, is outside
            ``MIN_PORT``-``MAX_PORT``, or ``start`` is greater than ``end``.
            argparse prints a usage message before exiting.
    """
    if isinstance(argv, (str, bytes)):
        raise TypeError("argv must be a list of strings, not a single string")
    parser = argparse.ArgumentParser(
        description="Scan open TCP ports on 127.0.0.1 and identify owning processes."
    )
    parser.add_argument("--start", type=int, default=MIN_PORT,
                        help=f"first port to scan (default {MIN_PORT})")
    parser.add_argument("--end", type=int, default=MAX_PORT,
                        help=f"last port to scan (default {MAX_PORT})")
    args = parser.parse_args(argv)

    for name in ("start", "end"):
        value = getattr(args, name)
        if not MIN_PORT <= value <= MAX_PORT:
            parser.error(f"--{name} must be between {MIN_PORT} and {MAX_PORT} (got {value})")
    if args.start > args.end:
        parser.error(f"--start ({args.start}) must not be greater than --end ({args.end})")
    return args


def is_port_open(port):
    """Check whether a TCP port on 127.0.0.1 accepts connections.

    Args:
        port (int): TCP port number to probe.

    Returns:
        bool: True if a TCP connect to ``127.0.0.1:port`` succeeds within
        ``CONNECT_TIMEOUT`` seconds, otherwise False.

    Raises:
        TypeError: If ``port`` is not an int.
        ValueError: If ``port`` is outside ``MIN_PORT``-``MAX_PORT``.
    """
    _check_port(port)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(CONNECT_TIMEOUT)
        return sock.connect_ex((HOST, port)) == 0


def scan_ports(start, end):
    """Scan a range of TCP ports on 127.0.0.1 concurrently.

    Args:
        start (int): First port to scan (inclusive).
        end (int): Last port to scan (inclusive).

    Returns:
        list[int]: The open ports in ``[start, end]``, sorted in ascending
        order.

    Raises:
        TypeError: If ``start`` or ``end`` is not an int.
        ValueError: If ``start`` or ``end`` is outside
            ``MIN_PORT``-``MAX_PORT``, or ``start`` is greater than ``end``.
    """
    _check_port(start, "start")
    _check_port(end, "end")
    if start > end:
        raise ValueError(f"start ({start}) must not be greater than end ({end})")
    ports = range(start, end + 1)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        results = pool.map(is_port_open, ports)
        return [p for p, is_open in zip(ports, results) if is_open]


def build_port_pid_map():
    """Map listening local TCP ports to the PIDs that own them.

    Only sockets in the LISTEN state are included. If several sockets listen
    on the same port, the first PID seen is kept.

    Returns:
        tuple[dict[int, int], str | None]: A ``(mapping, warning)`` pair.
        ``mapping`` maps port numbers to PIDs. ``warning`` is a message if
        the connection table could not be fully read (for example, without
        administrator/root rights), otherwise None.
    """
    mapping = {}
    warning = None
    try:
        conns = psutil.net_connections(kind="tcp")
    except (psutil.AccessDenied, PermissionError):
        return mapping, ("Permission denied reading system connections; "
                         "run as administrator/root for process attribution.")
    for conn in conns:
        if conn.status != psutil.CONN_LISTEN or not conn.laddr:
            continue
        if conn.pid is None:
            warning = ("Some ports have no visible PID; "
                       "run as administrator/root for full attribution.")
            continue
        mapping.setdefault(conn.laddr.port, conn.pid)
    return mapping, warning


def describe_process(pid):
    """Look up the name and executable path of a process.

    Failures do not raise; placeholder values are returned instead.

    Args:
        pid (int | None): Process ID to look up, or None if the owner of the
            port is unknown.

    Returns:
        tuple[str, str]: A ``(name, path)`` pair. The placeholders are
        ``("unknown", "unknown")`` when ``pid`` is None, ``("(exited)", "-")``
        when the process no longer exists, and ``("(access denied)", "-")``
        when its name cannot be read. If only the path cannot be read,
        ``path`` is ``"(access denied)"`` or ``"-"``.

    Raises:
        TypeError: If ``pid`` is neither None nor an int.
        ValueError: If ``pid`` is negative.
    """
    _check_pid(pid)
    if pid is None:
        return "unknown", "unknown"
    try:
        proc = psutil.Process(pid)
        name = proc.name()
    except psutil.NoSuchProcess:
        return "(exited)", "-"
    except psutil.AccessDenied:
        return "(access denied)", "-"
    try:
        path = proc.exe() or "-"
    except (psutil.AccessDenied, psutil.ZombieProcess):
        path = "(access denied)"
    except psutil.NoSuchProcess:
        path = "-"
    return name, path


def attribute_ports(open_ports):
    """Attach owning-process details to each open port.

    Args:
        open_ports (Iterable[int]): Open port numbers, in display order.

    Returns:
        tuple[list[tuple[int, int | None, str, str]], str | None]: A
        ``(rows, warning)`` pair. ``rows`` holds one
        ``(port, pid, name, path)`` tuple per open port, in input order;
        ``pid`` is None if no owner was found. ``warning`` is passed through
        from :func:`build_port_pid_map`.

    Raises:
        TypeError: If ``open_ports`` is not iterable or a port is not an int.
        ValueError: If a port is outside ``MIN_PORT``-``MAX_PORT``.
    """
    open_ports = list(open_ports)
    for port in open_ports:
        _check_port(port)
    port_pid, warning = build_port_pid_map()
    rows = []
    for port in open_ports:
        pid = port_pid.get(port)
        name, path = describe_process(pid)
        rows.append((port, pid, name, path))
    return rows, warning


# --- Flagging -------------------------------------------------------------

OK, REVIEW, SUSPICIOUS = "OK", "REVIEW", "SUSPICIOUS"
_SEVERITY = {OK: 0, REVIEW: 1, SUSPICIOUS: 2}
NO_EXPECTED_OWNER = frozenset()  # marker: port listed as "(none expected)"

# Well-known Windows process names used only for typosquat detection; the
# expected owners parsed from the mappings file are added to this set.
BASE_SYSTEM_PROCESSES = frozenset({
    "svchost", "lsass", "services", "wininit", "winlogon", "csrss", "smss",
    "spoolsv", "system", "explorer", "taskhostw", "dwm",
})
SUSPICIOUS_PATH_MARKERS = ("\\temp\\", "\\appdata\\", "\\downloads\\")


def _norm(name):
    """Normalise a process name for comparison.

    Args:
        name (str): Process name, e.g. ``" SvcHost.EXE "``.

    Returns:
        str: The name stripped of whitespace, lower-cased, and without a
        trailing ``.exe``, e.g. ``"svchost"``.

    Raises:
        TypeError: If ``name`` is not a str.
    """
    _check_str(name, "name")
    name = name.strip().lower()
    return name[:-4] if name.endswith(".exe") else name


def _parse_expected(cell):
    """Parse an 'Expected Process(es)' cell from the mappings table.

    Parenthesised comments are dropped and alternatives are separated by
    ``/``, so ``"System / svchost.exe (DNS Client)"`` gives
    ``frozenset({"system", "svchost"})``.

    Args:
        cell (str): Raw cell text.

    Returns:
        frozenset[str] | None: None if the owner varies (not checked) or the
        cell has no usable names, ``NO_EXPECTED_OWNER`` if no process is
        expected, otherwise a frozenset of normalised process names.

    Raises:
        TypeError: If ``cell`` is not a str.
    """
    _check_str(cell, "cell")
    text = cell.strip().lower()
    if text.startswith("varies"):
        return None
    if "none expected" in text:
        return NO_EXPECTED_OWNER
    text = re.sub(r"\(.*?\)", "", text)
    names = {_norm(part) for part in text.split("/") if part.strip()}
    return frozenset(names) or None


def load_expected_mappings(path=MAPPINGS_FILE):
    """Load the expected port -> process mappings from a markdown table.

    Only table rows whose first cell is a port number and whose protocol
    cell contains ``TCP`` are used; other lines are ignored. The file is
    only ever read, never written.

    Args:
        path (str): Path to the markdown file. Defaults to ``MAPPINGS_FILE``.

    Returns:
        tuple[dict[int, tuple[frozenset[str] | None, str]], str | None]: A
        ``(mappings, error)`` pair. ``mappings`` maps each port to
        ``(expected_owners, note)``, where ``expected_owners`` is as returned
        by :func:`_parse_expected`. ``error`` is a message if the file is
        missing, cannot be read or decoded, or has no usable rows (in which
        case ``mappings`` is empty), otherwise None.

    Raises:
        TypeError: If ``path`` is not a str or path-like object.
    """
    if not isinstance(path, (str, os.PathLike)):
        raise TypeError(f"path must be a str or path-like, got {type(path).__name__}")
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except FileNotFoundError:
        return {}, f"Mappings file not found: {path}"
    except (OSError, UnicodeDecodeError) as exc:
        return {}, f"Could not read mappings file {path}: {exc}"

    mappings = {}
    for line in lines:
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4 or not cells[0].isdigit():
            continue
        if "TCP" not in cells[1].upper():
            continue
        mappings[int(cells[0])] = (_parse_expected(cells[2]), cells[3])
    if not mappings:
        return {}, f"No port mappings found in {path}; check its table format."
    return mappings, None


def _standard_dirs():
    """List the standard Windows install directories.

    The directories come from the ``SystemRoot``, ``ProgramFiles`` and
    ``ProgramFiles(x86)`` environment variables; unset variables are skipped.

    Returns:
        tuple[str, ...]: Lower-case directory prefixes, each ending in a
        backslash, suitable for ``str.startswith``.
    """
    dirs = []
    for var in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)"):
        value = os.environ.get(var)
        if value:
            dirs.append(value.lower().rstrip("\\") + "\\")
    return tuple(dirs)


def _svchost_parent_issue(pid):
    """Check whether a svchost.exe process looks unparented or isolated.

    A genuine svchost.exe is started by services.exe, and several instances
    normally run at once.

    Args:
        pid (int | None): PID of the svchost.exe process.

    Returns:
        str | None: A reason string if the parent is not services.exe or
        only one svchost.exe is running, otherwise None. None is also
        returned if ``pid`` is None or the process details cannot be read.

    Raises:
        TypeError: If ``pid`` is neither None nor an int.
        ValueError: If ``pid`` is negative.
    """
    _check_pid(pid)
    if pid is None:
        return None  # psutil.Process(None) would inspect this script instead
    try:
        parent = psutil.Process(pid).parent()
        parent_name = parent.name() if parent else None
        count = sum(1 for p in psutil.process_iter(["name"])
                    if _norm(p.info.get("name") or "") == "svchost")
    except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
        return None  # cannot tell; do not guess
    if parent_name is None or _norm(parent_name) != "services":
        return f"svchost.exe parent is {parent_name or 'unknown'}, not services.exe"
    if count < 2:
        return "lone svchost.exe instance"
    return None


def flag_process(port, pid, name, path, mappings):
    """Decide the flag for one open port.

    The checks are: owner mismatch against ``mappings``, a port with no
    expected owner, a process name that mimics a system process, an
    unparented or lone svchost.exe, and the executable's install path. A
    process that could not be inspected is flagged REVIEW. The function is
    pure apart from the svchost.exe checks, which query psutil.

    Args:
        port (int): The open port number.
        pid (int | None): PID of the owning process, or None if unknown.
        name (str): Process name as returned by :func:`describe_process`.
        path (str): Executable path as returned by :func:`describe_process`.
        mappings (dict): Expected mappings as returned by
            :func:`load_expected_mappings`; may be empty.

    Returns:
        tuple[str, str]: A ``(flag, reason)`` pair. ``flag`` is OK, REVIEW or
        SUSPICIOUS (the most severe finding). ``reason`` joins the reasons at
        that severity plus any REVIEW reasons with ``"; "``, and is empty for
        OK.

    Raises:
        TypeError: If an argument has the wrong type.
        ValueError: If ``port`` is out of range or ``pid`` is negative.
    """
    _check_port(port)
    _check_pid(pid)
    _check_str(name, "name")
    _check_str(path, "path")
    if not isinstance(mappings, dict):
        raise TypeError(f"mappings must be a dict, got {type(mappings).__name__}")
    findings = []  # (severity, reason)
    norm_name = _norm(name)
    inspectable = not name.startswith("(") and name != "unknown"

    if not inspectable:
        findings.append((REVIEW, "process could not be inspected"))
    else:
        entry = mappings.get(port)
        if entry:
            expected, _note = entry
            if expected is NO_EXPECTED_OWNER:
                findings.append((SUSPICIOUS, "port has no expected owner"))
            elif expected is not None and norm_name not in expected:
                owners = ", ".join(sorted(expected))
                findings.append((SUSPICIOUS, f"expected owner: {owners}"))

        known = BASE_SYSTEM_PROCESSES | {
            n for e, _ in mappings.values() if e for n in e}
        if norm_name not in known and difflib.get_close_matches(
                norm_name, known, n=1, cutoff=0.8):
            findings.append((SUSPICIOUS, "name mimics a system process"))

        if norm_name == "svchost":
            issue = _svchost_parent_issue(pid)
            if issue:
                findings.append((SUSPICIOUS, issue))

    real_path = path.lower()
    if inspectable and os.path.isabs(path):
        if any(m in real_path for m in SUSPICIOUS_PATH_MARKERS):
            findings.append((SUSPICIOUS, "runs from temp/appdata/downloads"))
        elif not real_path.startswith(_standard_dirs()):
            findings.append((REVIEW, "non-standard install path"))

    if not findings:
        return OK, ""
    top = max(sev for sev, _ in findings)
    reasons = "; ".join(r for sev, r in findings if sev == top or sev == REVIEW)
    return top, reasons


def format_table(rows):
    """Render flagged rows as a left-aligned, fixed-width text table.

    Args:
        rows (list[tuple]): ``(port, pid, name, path, flag, reason)`` tuples.
            A ``pid`` of None is shown as ``"-"``.

    Returns:
        str: The table, with a header line and a dashed separator line,
        joined with newlines and without a trailing newline.

    Raises:
        ValueError: If a row is not a tuple or list of six values.
    """
    headers = ("PORT", "PID", "PROCESS", "PATH", "FLAG", "REASON")
    rows = list(rows)
    for i, row in enumerate(rows):
        if not isinstance(row, (tuple, list)) or len(row) != len(headers):
            raise ValueError(f"row {i} must be a tuple of {len(headers)} values, "
                             f"got {row!r}")
    str_rows = [(str(p), "-" if pid is None else str(pid), name, path, flag, reason)
                for p, pid, name, path, flag, reason in rows]
    widths = [max(len(h), *(len(r[i]) for r in str_rows)) if str_rows else len(h)
              for i, h in enumerate(headers)]
    line = "  ".join(f"{{:<{w}}}" for w in widths)
    out = [line.format(*headers), line.format(*("-" * w for w in widths))]
    out.extend(line.format(*r) for r in str_rows)
    return "\n".join(out)


def main(argv=None):
    """Run the scan and print the flagged results.

    The table and summary are printed to stdout. Permission and
    mappings-file warnings are printed to stderr.

    Args:
        argv (list[str] | None): Command-line arguments. If None,
            ``sys.argv[1:]`` is used.

    Returns:
        int: The process exit status (0 on success).

    Raises:
        TypeError: If ``argv`` is a single string (see :func:`parse_args`).
        SystemExit: If the arguments are invalid (see :func:`parse_args`).
    """
    args = parse_args(argv)
    print(f"Scanning {HOST} ports {args.start}-{args.end}...")
    open_ports = scan_ports(args.start, args.end)
    if not open_ports:
        print("No open TCP ports found.")
        return 0

    rows, warning = attribute_ports(open_ports)
    mappings, map_error = load_expected_mappings()
    flagged = [(port, pid, name, path, *flag_process(port, pid, name, path, mappings))
               for port, pid, name, path in rows]
    print(f"\n{len(flagged)} open port(s):\n")
    print(format_table(flagged))
    counts = {level: sum(1 for r in flagged if r[4] == level)
              for level in (SUSPICIOUS, REVIEW, OK)}
    print(f"\nSummary: {counts[SUSPICIOUS]} suspicious, "
          f"{counts[REVIEW]} to review, {counts[OK]} ok")
    if warning:
        print(f"\nWarning: {warning}", file=sys.stderr)
    if map_error:
        print(f"\nWarning: {map_error} Port/owner rules were skipped; "
              "only path and process-name checks were applied.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
