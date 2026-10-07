#!/usr/bin/env python3
"""ironwall - a small interactive iptables IP blocker for Linux (Alpine compatible).

Requires: python3, iptables, root privileges. Standard library only.
"""

import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    import readline  # noqa: F401  (enables arrow keys / history if available)
except ImportError:
    pass

PROMPT = "ironwall> "
BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "blocked_ips.json"
EXPORT_FILE = BASE_DIR / "blocklist.txt"
AUTH_LOG = Path("/var/log/auth.log")
FALLBACK_LOG = Path("/var/log/messages")  # Alpine's default syslog target
LOG_LINES = 20

IPV4_RE = re.compile(
    r"^(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)$"
)
FAILED_SSH_RE = re.compile(r"sshd.*(Failed password|Invalid user|authentication failure)")

HELP_TEXT = """\
Commands:
  block <ip>          Block an IPv4 address (iptables DROP) and save it
  unblock <ip>        Remove the block and delete it from storage
  list | blocklist    Show all blocked IPs
  logs                Show the last 20 failed SSH attempts
  scan --check <ip>   Check IP reputation (placeholder)
  export              Export blocked IPs to blocklist.txt
  help                Show this help
  clear               Clear the screen
  exit                Quit ironwall"""


# ---------- helpers ----------

def is_valid_ipv4(ip: str) -> bool:
    return bool(IPV4_RE.match(ip))


def load_db() -> list:
    """Return list of {"ip": ..., "blocked_at": ...} entries."""
    if not DB_FILE.exists():
        return []
    try:
        data = json.loads(DB_FILE.read_text())
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[!] Could not read {DB_FILE.name}: {exc}")
        return []


def save_db(entries: list) -> bool:
    try:
        DB_FILE.write_text(json.dumps(entries, indent=2) + "\n")
        return True
    except OSError as exc:
        print(f"[!] Could not write {DB_FILE.name}: {exc}")
        return False


def run_iptables(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["iptables", *args], capture_output=True, text=True, check=False
    )


def rule_exists(ip: str) -> bool:
    return run_iptables("-C", "INPUT", "-s", ip, "-j", "DROP").returncode == 0


# ---------- commands ----------

def cmd_block(args: list) -> None:
    if len(args) != 1:
        print("Usage: block <ip>")
        return
    ip = args[0]
    if not is_valid_ipv4(ip):
        print(f"[!] '{ip}' is not a valid IPv4 address.")
        return

    entries = load_db()
    if any(e["ip"] == ip for e in entries) and rule_exists(ip):
        print(f"[*] {ip} is already blocked.")
        return

    if not rule_exists(ip):
        result = run_iptables("-A", "INPUT", "-s", ip, "-j", "DROP")
        if result.returncode != 0:
            print(f"[!] iptables failed: {result.stderr.strip()}")
            return

    if not any(e["ip"] == ip for e in entries):
        entries.append({"ip": ip, "blocked_at": datetime.now().isoformat(timespec="seconds")})
        save_db(entries)
    print(f"[+] Blocked {ip}")


def cmd_unblock(args: list) -> None:
    if len(args) != 1:
        print("Usage: unblock <ip>")
        return
    ip = args[0]
    if not is_valid_ipv4(ip):
        print(f"[!] '{ip}' is not a valid IPv4 address.")
        return

    result = run_iptables("-D", "INPUT", "-s", ip, "-j", "DROP")
    if result.returncode != 0:
        print(f"[!] iptables: {result.stderr.strip() or 'rule not found'}")

    entries = load_db()
    remaining = [e for e in entries if e["ip"] != ip]
    if len(remaining) != len(entries):
        save_db(remaining)
        print(f"[+] Removed {ip} from blocklist.")
    elif result.returncode == 0:
        print(f"[+] Unblocked {ip}")
    else:
        print(f"[*] {ip} was not in the blocklist.")


def cmd_list(_args: list) -> None:
    entries = load_db()
    if not entries:
        print("No blocked IPs.")
        return
    print(f"{'IP ADDRESS':<18}BLOCKED AT")
    print("-" * 38)
    for e in entries:
        print(f"{e['ip']:<18}{e.get('blocked_at', 'unknown')}")
    print(f"\nTotal: {len(entries)}")


def cmd_logs(_args: list) -> None:
    log_path = AUTH_LOG if AUTH_LOG.exists() else FALLBACK_LOG
    if not log_path.exists():
        print(f"[!] Neither {AUTH_LOG} nor {FALLBACK_LOG} exists.")
        return
    if log_path != AUTH_LOG:
        print(f"[*] {AUTH_LOG} not found, using {log_path} instead.")
    try:
        with open(log_path, "r", errors="replace") as fh:
            failed = [line.rstrip() for line in fh if FAILED_SSH_RE.search(line)]
    except PermissionError:
        print(f"[!] Permission denied reading {log_path}. Run as root.")
        return
    except OSError as exc:
        print(f"[!] Could not read {log_path}: {exc}")
        return

    if not failed:
        print("No failed SSH attempts found.")
        return
    print(f"Last {min(LOG_LINES, len(failed))} failed SSH attempts:")
    for line in failed[-LOG_LINES:]:
        print(line)


def cmd_scan(args: list) -> None:
    if len(args) != 2 or args[0] != "--check":
        print("Usage: scan --check <ip>")
        return
    if not is_valid_ipv4(args[1]):
        print(f"[!] '{args[1]}' is not a valid IPv4 address.")
        return
    print("Checking VT....")


def cmd_export(_args: list) -> None:
    entries = load_db()
    try:
        EXPORT_FILE.write_text("".join(f"{e['ip']}\n" for e in entries))
    except OSError as exc:
        print(f"[!] Could not write {EXPORT_FILE.name}: {exc}")
        return
    print(f"[+] Exported {len(entries)} IP(s) to {EXPORT_FILE}")


def cmd_help(_args: list) -> None:
    print(HELP_TEXT)


def cmd_clear(_args: list) -> None:
    print("\033[2J\033[H", end="")  # ANSI; no dependency on the `clear` binary


def cmd_exit(_args: list) -> None:
    print("Goodbye.")
    sys.exit(0)


COMMANDS = {
    "block": cmd_block,
    "unblock": cmd_unblock,
    "list": cmd_list,
    "blocklist": cmd_list,
    "logs": cmd_logs,
    "scan": cmd_scan,
    "export": cmd_export,
    "help": cmd_help,
    "clear": cmd_clear,
    "exit": cmd_exit,
    "quit": cmd_exit,
}


# ---------- main ----------

def preflight() -> None:
    if os.geteuid() != 0:
        print("[!] ironwall must be run as root (try: sudo python3 ironwall.py)")
        sys.exit(1)
    try:
        subprocess.run(["iptables", "--version"], capture_output=True, check=True)
    except FileNotFoundError:
        print("[!] iptables not found. On Alpine: apk add iptables")
        sys.exit(1)
    except subprocess.CalledProcessError as exc:
        print(f"[!] iptables error: {exc}")
        sys.exit(1)


def main() -> None:
    preflight()
    print("IronWall - type 'help' for commands.")
    while True:
        try:
            line = input(PROMPT).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            cmd_exit([])
        if not line:
            continue
        try:
            parts = shlex.split(line)
        except ValueError as exc:
            print(f"[!] Parse error: {exc}")
            continue
        handler = COMMANDS.get(parts[0].lower())
        if handler is None:
            print(f"Unknown command '{parts[0]}'. Type 'help'.")
            continue
        handler(parts[1:])


if __name__ == "__main__":
    main()
