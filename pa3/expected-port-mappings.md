# Expected Port → Process Mappings

Reference list of common Windows ports and the process(es) that legitimately
own them. Use this to sanity-check scan results from the port scanner tool —
anything bound to an unexpected process, or a port with "(none expected)"
that shows as open, is worth investigating.

## Common Ports

| Port | Protocol | Expected Process(es)      | Notes                                                              |
|------|----------|----------------------------|----------------------------------------------------------------------|
| 21   | TCP      | (none expected)            | FTP — legacy, unencrypted. Should not be running unless intentionally hosting FTP. |
| 22   | TCP      | sshd.exe / OpenSSH         | SSH — fine if you intentionally installed OpenSSH Server.            |
| 23   | TCP      | (none expected)            | Telnet — legacy, unencrypted. Should never be open on a modern PC.   |
| 25   | TCP      | (none expected)            | SMTP — mail relay. Suspicious on a personal workstation.             |
| 53   | TCP/UDP  | svchost.exe (DNS Client)   | DNS. Normal if a local resolver/VPN client is running.               |
| 80   | TCP      | Varies (browser, IIS, dev server) | Only suspicious if you're not running a web server/dev tool.  |
| 135  | TCP      | svchost.exe                | RPC endpoint mapper — normal Windows service.                        |
| 139  | TCP      | System                     | NetBIOS Session Service — normal on Windows if file sharing enabled. |
| 443  | TCP      | Varies (browser, dev server) | Same as 80 — expected only if you're running something intentionally. |
| 445  | TCP      | System / svchost.exe       | SMB — file/printer sharing. Should be owned by System or Server service. |
| 3389 | TCP      | svchost.exe                | RDP — Remote Desktop. Should only be open if you enabled Remote Desktop. |
| 5000 | TCP      | Varies (python.exe, node.exe) | Common dev server port — expected only during active development.  |
| 5357 | TCP      | svchost.exe                 | WSDAPI / Network Discovery — normal if device discovery is on.      |

## Known-Suspicious Indicators

- **Port/process mismatch** — a well-known port (e.g. 445, 3389) bound to a
  process other than its expected owner.
- **Unusual install path** — process executable running from `%TEMP%`,
  `%APPDATA%`, `Downloads`, or another non-standard location instead of
  `C:\Windows\System32` or `C:\Program Files\...`.
- **Typosquatted process names** — names that mimic legitimate system
  processes, e.g. `scvhost.exe`, `svch0st.exe`, `svchost32.exe`.
- **Lone/unparented svchost.exe** — a real `svchost.exe` is normally spawned
  by `services.exe` and multiple instances run simultaneously. A single
  isolated instance with no expected parent relationship is worth checking.
- **"System" claims without a matching Windows feature enabled** — e.g. port
  445 showing under `System` when file/printer sharing is turned off.
- **Unsigned or unfamiliar executables** on any listening port, regardless of
  which port it is.

## How to Use

1. Run the port scanner tool.
2. For each open port + owning process reported, check this table.
3. If the process doesn't match the expected owner, or the port is marked
   "(none expected)" but is open, flag it for further investigation
   (e.g. check the executable's file path, digital signature, and parent
   process).
