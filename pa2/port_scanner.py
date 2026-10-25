"""Localhost port scanner + process attribution.

Scans TCP ports on 127.0.0.1 only, then uses psutil to identify the process
that owns each open port and prints a summary table.
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


def parse_args(argv=None):
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
    """Return True if a TCP connect to 127.0.0.1:port succeeds."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(CONNECT_TIMEOUT)
        return sock.connect_ex((HOST, port)) == 0


def scan_ports(start, end):
    """Return a sorted list of open ports in [start, end] on 127.0.0.1."""
    ports = range(start, end + 1)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        results = pool.map(is_port_open, ports)
        return [p for p, is_open in zip(ports, results) if is_open]


def build_port_pid_map():
    """Map listening local ports to PIDs using psutil.

    Returns (mapping, warning). warning is a message if the process table
    could not be fully read (e.g. missing admin rights), else None.
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
    """Return (name, path) for a PID, degrading gracefully on errors."""
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
    """Return (rows, warning); rows are (port, pid, name, path) tuples."""
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
    name = name.strip().lower()
    return name[:-4] if name.endswith(".exe") else name


def _parse_expected(cell):
    """Parse an 'Expected Process(es)' cell.

    Returns None if the owner varies (not checked), NO_EXPECTED_OWNER if none
    is expected, otherwise a frozenset of normalised process names.
    """
    text = cell.strip().lower()
    if text.startswith("varies"):
        return None
    if "none expected" in text:
        return NO_EXPECTED_OWNER
    text = re.sub(r"\(.*?\)", "", text)
    names = {_norm(part) for part in text.split("/") if part.strip()}
    return frozenset(names) or None


def load_expected_mappings(path=MAPPINGS_FILE):
    """Read port -> (expected owners, note) from the markdown table.

    Returns (mappings, error). The file is only ever read, never written.
    """
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
    dirs = []
    for var in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)"):
        value = os.environ.get(var)
        if value:
            dirs.append(value.lower().rstrip("\\") + "\\")
    return tuple(dirs)


def _svchost_parent_issue(pid):
    """Return a reason string if a svchost.exe looks unparented, else None."""
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
    """Return (flag, reason) for one open port. Pure apart from svchost checks."""
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
    headers = ("PORT", "PID", "PROCESS", "PATH", "FLAG", "REASON")
    str_rows = [(str(p), "-" if pid is None else str(pid), name, path, flag, reason)
                for p, pid, name, path, flag, reason in rows]
    widths = [max(len(h), *(len(r[i]) for r in str_rows)) if str_rows else len(h)
              for i, h in enumerate(headers)]
    line = "  ".join(f"{{:<{w}}}" for w in widths)
    out = [line.format(*headers), line.format(*("-" * w for w in widths))]
    out.extend(line.format(*r) for r in str_rows)
    return "\n".join(out)


def main(argv=None):
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
