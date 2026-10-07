# IronWall

A small, easy command-line firewall helper for Linux. It lets you block and unblock IP addresses using `iptables`, keeps a record of what you blocked, and helps you spot failed SSH login attempts.

Works on Alpine Linux, and also on Debian, Ubuntu, Fedora and most other Linux systems.

---

## 1. What is IronWall for?

If your server is online, strangers will try to log in to it (usually over SSH). You will see many "Failed password" messages in your logs. IronWall helps you:

1. **See** who is failing to log in (`logs`)
2. **Block** an attacker's IP address with one short command (`block`)
3. **Unblock** an IP if you blocked it by mistake (`unblock`)
4. **Keep a list** of everything you blocked (`list`)
5. **Export** that list to a text file (`export`)

You do not need to remember long `iptables` commands. IronWall runs them for you and stores the list in a JSON file.

---

## 2. What you need

| Requirement | Why |
|---|---|
| Linux | IronWall uses `iptables` |
| Python 3 | The tool is written in Python (no extra packages needed) |
| `iptables` | Does the real blocking |
| Root access (`sudo`) | Changing firewall rules needs admin rights |

---

## 3. Installation (step by step)

### Step 1: Install Python 3 and iptables

**Alpine Linux**
```sh
apk add python3 iptables
```

**Debian / Ubuntu**
```sh
sudo apt update
sudo apt install python3 iptables
```

**Fedora / RHEL**
```sh
sudo dnf install python3 iptables
```

### Step 2: Put the file in a folder

Place `ironwall.py` in any folder, for example:
```sh
mkdir ~/ironwall
cd ~/ironwall
# copy ironwall.py into this folder
```

### Step 3: Check it is there
```sh
ls
```
You should see `ironwall.py`.

### Step 4 (optional): Make it executable
```sh
chmod +x ironwall.py
```

---

## 4. Starting the tool

IronWall **must run as root**.

```sh
sudo python3 ironwall.py
```

On Alpine, if you are already root:
```sh
python3 ironwall.py
```

If you use `doas` instead of `sudo`:
```sh
doas python3 ironwall.py
```

You will see:
```
IronWall - type 'help' for commands.
ironwall>
```

Now type commands at the `ironwall>` prompt.

If you forget root, you will see an error like this and the tool will close:
```
[!] ironwall must be run as root (try: sudo python3 ironwall.py)
```

---

## 5. Commands

### `help`
Shows all commands.
```
ironwall> help
```

### `block <ip>`
Blocks an IPv4 address. All traffic from this IP to your machine is dropped.
```
ironwall> block 203.0.113.50
[+] Blocked 203.0.113.50
```
- The IP is checked first. Invalid IPs like `999.1.1.1` or `abc` are rejected.
- Under the hood it runs: `iptables -A INPUT -s 203.0.113.50 -j DROP`
- The IP is saved to `blocked_ips.json`.
- Blocking the same IP twice does not create a duplicate rule.

### `unblock <ip>`
Removes the block.
```
ironwall> unblock 203.0.113.50
[+] Removed 203.0.113.50 from blocklist.
```
- Under the hood it runs: `iptables -D INPUT -s 203.0.113.50 -j DROP`
- The IP is also removed from `blocked_ips.json`.

### `list` (or `blocklist`)
Shows every IP you have blocked, with the date and time.
```
ironwall> list
IP ADDRESS        BLOCKED AT
--------------------------------------
203.0.113.50      2026-10-07T14:32:10

Total: 1
```

### `logs`
Shows the **last 20 failed SSH login attempts** from `/var/log/auth.log`.
```
ironwall> logs
```
- On Alpine Linux, `/var/log/auth.log` often does not exist. IronWall then reads `/var/log/messages` automatically and tells you it did so.
- Look at the IP addresses in the output. If one IP appears many times, it is probably an attacker, so use `block` on it.

### `scan --check <ip>`
A **placeholder** for checking an IP's reputation (for example on VirusTotal). Right now it only prints:
```
ironwall> scan --check 203.0.113.50
Checking VT....
```
It does not contact any website yet.

### `export`
Writes all blocked IPs to `blocklist.txt` (one IP per line) in the same folder as the script.
```
ironwall> export
[+] Exported 1 IP(s) to /home/user/ironwall/blocklist.txt
```

### `clear`
Clears the screen.

### `exit`
Leaves IronWall. (`quit`, Ctrl+C and Ctrl+D also work.)

---

## 6. A simple example session

```
$ sudo python3 ironwall.py
IronWall - type 'help' for commands.

ironwall> logs
Oct  7 14:01:22 server sshd[1234]: Failed password for root from 203.0.113.50 port 51234 ssh2
Oct  7 14:01:25 server sshd[1236]: Failed password for root from 203.0.113.50 port 51240 ssh2
...

ironwall> block 203.0.113.50
[+] Blocked 203.0.113.50

ironwall> list
IP ADDRESS        BLOCKED AT
--------------------------------------
203.0.113.50      2026-10-07T14:32:10

ironwall> export
[+] Exported 1 IP(s) to /home/user/ironwall/blocklist.txt

ironwall> exit
Goodbye.
```

---

## 7. Files IronWall creates

Both files are created in the **same folder as `ironwall.py`**.

| File | Purpose |
|---|---|
| `blocked_ips.json` | Memory of blocked IPs (created on first `block`) |
| `blocklist.txt` | Plain text list (created by `export`) |

Example `blocked_ips.json`:
```json
[
  {
    "ip": "203.0.113.50",
    "blocked_at": "2026-10-07T14:32:10"
  }
]
```

---

## 8. Checking the firewall yourself

To confirm the rules really exist, run this in a normal shell:
```sh
sudo iptables -L INPUT -n --line-numbers
```
You will see `DROP` rules for each blocked IP.

---

## 9. Important things to know

- **Do not block your own IP.** If you are connected by SSH and block your own address, you will lose access to the server. Check the IP first.
- **Rules disappear after reboot.** `iptables` rules are stored in memory only. The JSON file keeps your list, but the rules are not re-applied automatically. To keep rules after a reboot:
  - Alpine: `rc-service iptables save` (and `rc-update add iptables` to load them at boot)
  - Debian/Ubuntu: install `iptables-persistent`, then run `sudo netfilter-persistent save`
- **No auto-unblock.** A blocked IP stays blocked until you run `unblock`.
- **IPv4 only.** IPv6 addresses are not supported.
- **`scan` is a placeholder.** It does not check reputation yet.
- **Only `INPUT` rules.** IronWall blocks incoming traffic only.

---

## 10. Troubleshooting

| Problem | Solution |
|---|---|
| `must be run as root` | Start it with `sudo python3 ironwall.py` |
| `iptables not found` | Install it: `apk add iptables` (Alpine) or `sudo apt install iptables` (Debian/Ubuntu) |
| `python3: not found` | Install Python: `apk add python3` or `sudo apt install python3` |
| `is not a valid IPv4 address` | Check the IP: four numbers from 0 to 255 separated by dots, like `192.168.1.10` |
| `logs` shows nothing | Your system may log SSH elsewhere, or there were no failed attempts. Make sure SSH is running and logging |
| `Permission denied` reading logs | Run IronWall as root |
| iptables error about "can't initialize" or "Permission denied" | Make sure you are root. In containers (Docker/LXC), the container may need the `NET_ADMIN` permission |

---

## 11. Quick command cheat sheet

```
help                  show commands
block <ip>            block an IP
unblock <ip>          unblock an IP
list                  show blocked IPs   (also: blocklist)
logs                  last 20 failed SSH attempts
scan --check <ip>     placeholder reputation check
export                save blocked IPs to blocklist.txt
clear                 clear screen
exit                  quit
```

---

## 12. Safety note

Only use IronWall on systems you own or are allowed to manage. Blocking the wrong IP can cut off real users, so double-check before pressing Enter.
