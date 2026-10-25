import os
import tempfile
import unittest
from collections import namedtuple
from unittest import mock

import psutil

import port_scanner as ps

TABLE = """\
| Port | Protocol | Expected Process(es) | Notes |
|------|----------|----------------------|-------|
| 23   | TCP      | (none expected)      | Telnet |
| 53   | TCP/UDP  | svchost.exe (DNS Client) | DNS |
| 80   | TCP      | Varies (browser, IIS) | web |
| 445  | TCP      | System / svchost.exe | SMB |
"""

Addr = namedtuple("Addr", "ip port")
Conn = namedtuple("Conn", "laddr status pid")
WIN = "C:\\Windows\\System32\\"


class ParseExpectedTests(unittest.TestCase):
    def test_none_expected(self):
        """Check that "(none expected)" maps to the NO_EXPECTED_OWNER sentinel."""
        self.assertIs(ps._parse_expected("(none expected)"), ps.NO_EXPECTED_OWNER)

    def test_varies_is_unchecked(self):
        """Check that a "Varies" entry parses to None, meaning no owner check."""
        self.assertIsNone(ps._parse_expected("Varies (python.exe, node.exe)"))

    def test_multiple_and_parenthetical(self):
        """Check that multiple owners are split and parenthetical notes are dropped."""
        self.assertEqual(ps._parse_expected("System / svchost.exe"),
                         frozenset({"system", "svchost"}))
        self.assertEqual(ps._parse_expected("svchost.exe (DNS Client)"),
                         frozenset({"svchost"}))


class LoadMappingsTests(unittest.TestCase):
    def _write(self, text):
        """Write text to a temporary Markdown file and return its path.

        The file is removed automatically when the test finishes.
        """
        fd, path = tempfile.mkstemp(suffix=".md")
        os.close(fd)
        self.addCleanup(os.remove, path)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def test_parses_table(self):
        """Check that a well-formed table yields the expected port mappings."""
        mappings, err = ps.load_expected_mappings(self._write(TABLE))
        self.assertIsNone(err)
        self.assertEqual(set(mappings), {23, 53, 80, 445})
        self.assertIs(mappings[23][0], ps.NO_EXPECTED_OWNER)

    def test_missing_file(self):
        """Check that a missing file returns empty mappings and a "not found" error."""
        mappings, err = ps.load_expected_mappings("does-not-exist.md")
        self.assertEqual(mappings, {})
        self.assertIn("not found", err)

    def test_no_table(self):
        """Check that a file without a table returns empty mappings and an error."""
        mappings, err = ps.load_expected_mappings(self._write("# nothing here"))
        self.assertEqual(mappings, {})
        self.assertIn("No port mappings", err)

    def test_real_file_parses(self):
        """Check that the real expected-port-mappings file parses and lists port 445."""
        mappings, err = ps.load_expected_mappings()
        self.assertIsNone(err)
        self.assertIn(445, mappings)


class FlagProcessTests(unittest.TestCase):
    def setUp(self):
        """Load mappings from a temporary table and patch the standard directories."""
        fd, path = tempfile.mkstemp(suffix=".md")
        os.close(fd)
        self.addCleanup(os.remove, path)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(TABLE)
        self.mappings, _ = ps.load_expected_mappings(path)
        patcher = mock.patch.object(
            ps, "_standard_dirs", return_value=("c:\\windows\\", "c:\\program files\\"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def flag(self, port, name, path, pid=1):
        """Flag a process on a port using the test mappings.

        Returns the (flag, reason) tuple from flag_process.
        """
        return ps.flag_process(port, pid, name, path, self.mappings)

    def test_expected_owner_ok(self):
        """Check that the expected owner of a port is flagged OK."""
        self.assertEqual(self.flag(445, "System", "-"), (ps.OK, ""))

    def test_none_expected_port_open(self):
        """Check that an open port with no expected owner is flagged suspicious."""
        flag, reason = self.flag(23, "telnetd.exe", WIN + "telnetd.exe")
        self.assertEqual(flag, ps.SUSPICIOUS)
        self.assertIn("no expected owner", reason)

    def test_owner_mismatch(self):
        """Check that an unexpected owner on a mapped port is flagged suspicious."""
        flag, reason = self.flag(445, "evil.exe", WIN + "evil.exe")
        self.assertEqual(flag, ps.SUSPICIOUS)
        self.assertIn("expected owner", reason)

    def test_varies_port_not_checked(self):
        """Check that ports marked "Varies" skip the owner check."""
        self.assertEqual(self.flag(80, "nginx.exe", "C:\\Program Files\\n\\nginx.exe")[0],
                         ps.OK)

    def test_unlisted_port_ok(self):
        """Check that a legitimate process on an unlisted port is flagged OK."""
        self.assertEqual(self.flag(9999, "lsass.exe", WIN + "lsass.exe")[0], ps.OK)

    def test_typosquat(self):
        """Check that names imitating system processes are flagged as suspicious."""
        for name in ("scvhost.exe", "svch0st.exe", "svchost32.exe"):
            with self.subTest(name=name):
                flag, reason = self.flag(9999, name, WIN + name)
                self.assertEqual(flag, ps.SUSPICIOUS)
                self.assertIn("mimics", reason)

    def test_suspicious_path(self):
        """Check that executables in temp or download folders are flagged suspicious."""
        for path in ("C:\\Users\\a\\AppData\\Local\\Temp\\x.exe",
                     "C:\\Users\\a\\Downloads\\x.exe"):
            with self.subTest(path=path):
                self.assertEqual(self.flag(9999, "x.exe", path)[0], ps.SUSPICIOUS)

    def test_non_standard_path_is_review(self):
        """Check that an executable outside standard directories is flagged REVIEW."""
        self.assertEqual(self.flag(9999, "x.exe", "D:\\tools\\x.exe")[0], ps.REVIEW)

    def test_uninspectable_is_review(self):
        """Check that processes that cannot be inspected are flagged REVIEW."""
        for name in ("(access denied)", "(exited)", "unknown"):
            with self.subTest(name=name):
                self.assertEqual(self.flag(445, name, "-")[0], ps.REVIEW)

    def test_svchost_bad_parent(self):
        """Check that an svchost.exe with a wrong parent is flagged suspicious."""
        with mock.patch.object(ps, "_svchost_parent_issue",
                               return_value="svchost.exe parent is cmd.exe, not services.exe"):
            flag, reason = self.flag(53, "svchost.exe", WIN + "svchost.exe")
        self.assertEqual(flag, ps.SUSPICIOUS)
        self.assertIn("parent", reason)

    def test_svchost_healthy(self):
        """Check that an svchost.exe with no parent issue is flagged OK."""
        with mock.patch.object(ps, "_svchost_parent_issue", return_value=None):
            self.assertEqual(self.flag(53, "svchost.exe", WIN + "svchost.exe")[0], ps.OK)


class SvchostParentTests(unittest.TestCase):
    def _run(self, parent_name, count):
        """Run the svchost parent check against mocked psutil state.

        Args:
            parent_name: Name reported by the mocked parent process.
            count: Number of svchost.exe processes reported as running.

        Returns:
            The result of _svchost_parent_issue for PID 10.
        """
        parent = mock.Mock()
        parent.name.return_value = parent_name
        procs = [mock.Mock(info={"name": "svchost.exe"}) for _ in range(count)]
        with mock.patch.object(ps.psutil, "Process") as proc_cls, \
                mock.patch.object(ps.psutil, "process_iter", return_value=procs):
            proc_cls.return_value.parent.return_value = parent
            return ps._svchost_parent_issue(10)

    def test_healthy(self):
        """Check that a services.exe parent with several svchost peers is healthy."""
        self.assertIsNone(self._run("services.exe", 3))

    def test_wrong_parent(self):
        """Check that a parent other than services.exe is reported."""
        self.assertIn("not services.exe", self._run("cmd.exe", 3))

    def test_lone(self):
        """Check that a lone svchost.exe instance is reported."""
        self.assertIn("lone", self._run("services.exe", 1))

    def test_access_denied_does_not_guess(self):
        """Check that an access-denied error yields no issue rather than a guess."""
        with mock.patch.object(ps.psutil, "Process", side_effect=psutil.AccessDenied()):
            self.assertIsNone(ps._svchost_parent_issue(10))


class AttributionTests(unittest.TestCase):
    def test_port_pid_map_listening_only(self):
        """Check that only listening connections with a visible PID are mapped."""
        conns = [Conn(Addr("127.0.0.1", 80), psutil.CONN_LISTEN, 5),
                 Conn(Addr("127.0.0.1", 81), psutil.CONN_ESTABLISHED, 6),
                 Conn(Addr("127.0.0.1", 82), psutil.CONN_LISTEN, None)]
        with mock.patch.object(ps.psutil, "net_connections", return_value=conns):
            mapping, warning = ps.build_port_pid_map()
        self.assertEqual(mapping, {80: 5})
        self.assertIn("no visible PID", warning)

    def test_port_pid_map_access_denied(self):
        """Check that a permission error yields an empty map and a warning."""
        with mock.patch.object(ps.psutil, "net_connections",
                               side_effect=psutil.AccessDenied()):
            mapping, warning = ps.build_port_pid_map()
        self.assertEqual(mapping, {})
        self.assertIn("Permission denied", warning)

    def test_describe_none_pid(self):
        """Check that a missing PID is described as unknown."""
        self.assertEqual(ps.describe_process(None), ("unknown", "unknown"))

    def test_describe_no_such_process(self):
        """Check that a vanished process is described as exited."""
        with mock.patch.object(ps.psutil, "Process", side_effect=psutil.NoSuchProcess(1)):
            self.assertEqual(ps.describe_process(1), ("(exited)", "-"))

    def test_describe_access_denied_on_exe(self):
        """Check that a denied executable lookup keeps the name and marks the path."""
        proc = mock.Mock()
        proc.name.return_value = "x.exe"
        proc.exe.side_effect = psutil.AccessDenied()
        with mock.patch.object(ps.psutil, "Process", return_value=proc):
            self.assertEqual(ps.describe_process(1), ("x.exe", "(access denied)"))

    def test_describe_ok(self):
        """Check that a readable process returns its name and executable path."""
        proc = mock.Mock()
        proc.name.return_value = "x.exe"
        proc.exe.return_value = "C:\\x.exe"
        with mock.patch.object(ps.psutil, "Process", return_value=proc):
            self.assertEqual(ps.describe_process(1), ("x.exe", "C:\\x.exe"))

    def test_attribute_ports(self):
        """Check that ports are paired with PIDs, leaving unmapped ports without one."""
        with mock.patch.object(ps, "build_port_pid_map", return_value=({80: 5}, None)), \
                mock.patch.object(ps, "describe_process", return_value=("x.exe", "C:\\x.exe")):
            rows, warning = ps.attribute_ports([80, 81])
        self.assertIsNone(warning)
        self.assertEqual(rows[0], (80, 5, "x.exe", "C:\\x.exe"))
        self.assertEqual(rows[1][1], None)


class ArgsAndTableTests(unittest.TestCase):
    def test_defaults(self):
        """Check that the default port range is 1 through 65535."""
        args = ps.parse_args([])
        self.assertEqual((args.start, args.end), (1, 65535))

    def test_invalid_args_exit(self):
        """Check that invalid port arguments cause the parser to exit."""
        for argv in (["--start", "0"], ["--end", "70000"],
                     ["--start", "10", "--end", "5"], ["--start", "abc"]):
            with self.subTest(argv=argv), mock.patch("sys.stderr"):
                with self.assertRaises(SystemExit):
                    ps.parse_args(argv)

    def test_format_table(self):
        """Check that the table has a header, a separator, and one data row."""
        out = ps.format_table([(80, 5, "x.exe", "C:\\x.exe", ps.OK, "")])
        lines = out.splitlines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("PORT"))
        self.assertIn("x.exe", lines[2])

    def test_scan_only_targets_localhost(self):
        """Check that port probing connects only to 127.0.0.1."""
        with mock.patch.object(ps.socket, "socket") as sock_cls:
            sock = sock_cls.return_value.__enter__.return_value
            sock.connect_ex.return_value = 0
            self.assertTrue(ps.is_port_open(8080))
            sock.connect_ex.assert_called_once_with(("127.0.0.1", 8080))


if __name__ == "__main__":
    unittest.main()
