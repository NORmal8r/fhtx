#!/usr/bin/env python3
# fhtx.py — Termux-native scanner · deriver · connector
# Python 3.8+ | Termux on Android 8–14
# Developed by NORmal8r
#
# ⚠️ لأغراض تعليمية فقط. لا تستخدم ضد أي شخص. 
# اختبر شبكتك الخاصة، غيّر كلمة المرور الافتراضية، واحمِ نفسك.

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass

SSID_RE = re.compile(r"^fh[_-]?([0-9a-fA-F]{6})$", re.IGNORECASE)
COMP = {format(i, "x"): format(15 - i, "x") for i in range(16)}

class C:
    R, B, DIM = "\033[0m", "\033[1m", "\033[2m"
    CYAN, GREEN, YELLOW, RED, MAGENTA, BLUE, WHITE = (
        "\033[36m", "\033[32m", "\033[33m", "\033[31m", "\033[35m", "\033[34m", "\033[37m"
    )

_USE_COLOR = sys.stdout.isatty()

def c(text: str, *codes: str) -> str:
    if not _USE_COLOR or not codes: return text
    return "".join(codes) + text + C.R

def say(*args, **kw) -> None:
    print(*args, **kw)

def has(cmd: str) -> bool:
    return shutil.which(cmd) is not None

def has_root() -> bool:
    if not has("su"): return False
    try:
        r = subprocess.run(["su", "-c", "id -u"], capture_output=True, text=True, timeout=3)
        return r.returncode == 0 and r.stdout.strip() == "0"
    except Exception:
        return False

def has_adb() -> bool:
    if not has("adb"): return False
    try:
        r = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
        return "localhost" in r.stdout or "device" in r.stdout
    except Exception:
        return False

def root(cmd: str, timeout: int = 25) -> str | None:
    try:
        r = subprocess.run(["su", "-c", cmd], capture_output=True, text=True, errors="ignore", timeout=timeout)
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None

def adb(cmd: str, timeout: int = 20) -> str | None:
    try:
        r = subprocess.run(["adb", "shell", cmd], capture_output=True, text=True, errors="ignore", timeout=timeout)
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None

def toast(msg: str) -> None:
    if has("termux-toast"):
        try:
            subprocess.run(["termux-toast", "-g", "top", msg], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL, timeout=2)
        except Exception:
            pass

def clip(text: str) -> bool:
    if not has("termux-clipboard-set"): return False
    try:
        subprocess.run(["termux-clipboard-set", text], timeout=3, check=True, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False

@dataclass
class Net:
    ssid: str
    signal: int = 0
    security: str = "?"
    bssid: str = ""

    @property
    def derivable(self) -> bool:
        return SSID_RE.match(self.ssid) is not None

    @property
    def bars(self) -> str:
        if self.signal >= 75: return "▂▄▆█"
        if self.signal >= 50: return "▂▄▆·"
        if self.signal >= 25: return "▂▄··"
        return "▂···"

def rssi_pct(rssi: float) -> int:
    return max(0, min(100, int(2 * (rssi + 100))))

def scan_all() -> tuple[list[Net], str]:
    nets = []
    source = "none"
    out = None
    
    if has_root():
        out = root("cmd wifi list-scan-results")
        if out: source = "root"
    elif has_adb():
        out = adb("cmd wifi list-scan-results")
        if out: source = "adb"
    
    if not out and has("termux-wifi-scaninfo"):
        try:
            r = subprocess.run(["termux-wifi-scaninfo"], capture_output=True, text=True, timeout=20)
            data = json.loads(r.stdout or "[]")
            for n in data:
                ssid = n.get("SSID") or n.get("ssid") or ""
                if ssid:
                    nets.append(Net(ssid, rssi_pct(float(n.get("RSSI", -90))), "WPA2" if "WPA" in (n.get("capabilities") or "") else "OPEN", n.get("BSSID", "")))
            if nets: return _dedupe(nets), "termux-api"
        except Exception:
            pass

    if out:
        for m in re.finditer(r"SSID:\s*(.+?),\s*BSSID:\s*([0-9a-fA-F:]+),\s*(?:.*?)RSSI:\s*(-?\d+)(?:.*?capabilities:\s*(\S+))?", out):
            ssid = m.group(1).strip()
            if not ssid: continue
            cap = m.group(4) or ""
            sec = "WPA3" if "WPA3" in cap else "WPA2" if "WPA2" in cap else "WPA" if "WPA" in cap else "?"
            nets.append(Net(ssid, rssi_pct(int(m.group(3))), sec, m.group(2)))
    
    return (_dedupe(nets), source) if nets else ([], "none")

def _dedupe(nets: list[Net]) -> list[Net]:
    by: dict[str, Net] = {}
    for n in nets:
        if not n.ssid: continue
        prev = by.get(n.ssid)
        if prev is None or n.signal > prev.signal:
            by[n.ssid] = n
    return sorted(by.values(), key=lambda x: -x.signal)

def derive(ssid: str) -> str | None:
    m = SSID_RE.match(ssid.strip())
    return "wlan" + "".join(COMP[x] for x in m.group(1).lower()) if m else None

def connect(ssid: str, pwd: str) -> tuple[bool, str]:
    if has_root():
        out = root(f'cmd wifi connect-network "{ssid}" wpa2 "{pwd}"', timeout=30)
        if out is not None:
            return True, f"auto-connected via root ({ssid})"
    
    if has_adb():
        out = adb(f'cmd wifi connect-network "{ssid}" wpa2 "{pwd}"', timeout=20)
        if out is not None:
            return True, f"auto-connected via ADB ({ssid})"

    copied = clip(pwd)
    hint = f"copied to clipboard. Open WiFi settings and paste ({ssid})" if copied else f"password: {pwd} (connect manually)"
    try:
        subprocess.run(["am", "start", "-a", "android.settings.WIFI_SETTINGS"], stderr=subprocess.DEVNULL, timeout=5)
    except Exception:
        pass
    return False, hint

def banner() -> None:
    say()
    say(c("  ╔══════════════════════════════════════════════════════╗", C.CYAN))
    say(c("  ║  ", C.CYAN) + c("fhtx", C.WHITE, C.B) + c("  ·  fh_* deriver  ·  termux edition", C.CYAN) + c("         ║", C.CYAN))
    say(c("  ║  ", C.CYAN) + c("developed by NORmal8r", C.MAGENTA, C.B) + c("                               ║", C.CYAN))
    say(c("  ╚══════════════════════════════════════════════════════╝", C.CYAN))
    say()
    say(c("  [!] ", C.YELLOW, C.B) + c("لأغراض تعليمية فقط. لا تستخدم ضد أي شخص.", C.YELLOW))
    say(c("      ", C.YELLOW) + c("اختبر شبكتك الخاصة، غيّر كلمة المرور، واحمِ نفسك.", C.YELLOW))
    say()
    
    mode = c("root", C.GREEN, C.B) if has_root() else c("adb", C.GREEN, C.B) if has_adb() else c("non-root", C.YELLOW, C.B)
    api  = c("termux-api", C.GREEN) if has("termux-wifi-scaninfo") else c("none", C.RED)
    say(c(f"  system : {mode}  ·  scan : {api}", C.DIM))
    say(c("  " + "─" * 56, C.DIM))

def render(nets: list[Net], source: str) -> None:
    say()
    if source != "none":
        say(c(f"  networks found: {len(nets)}  ·  source: {source}", C.DIM))
    say()
    say(c(f"  {'#':>3}  {'SSID':<26} {'signal':<12} {'sec':<9} fh_*", C.B, C.WHITE))
    say(c("  " + "─" * 56, C.DIM))
    for i, n in enumerate(nets, 1):
        bar_col = C.GREEN if n.signal >= 70 else C.YELLOW if n.signal >= 40 else C.RED
        sig = c(f"{n.bars} {n.signal:>3}%", bar_col)
        flag = c("✔", C.GREEN) if n.derivable else c("·", C.DIM)
        say(f"  {i:>3}  {n.ssid:<26} {sig:<20} {n.security:<9} {flag}")
    say()

def ask(prompt: str, default: str = "") -> str:
    try:
        return input(c(prompt, C.CYAN) + (c(f" [{default}]", C.DIM) if default else "") + ": ").strip() or default
    except (KeyboardInterrupt, EOFError):
        say()
        sys.exit(0)

def do_target(n: Net) -> None:
    say()
    say(c("  ┌── target ", C.DIM) + c("──────────────────────────────────────", C.DIM))
    say(c("  │  SSID     ", C.DIM) + c(f"{n.ssid}", C.B, C.WHITE))
    
    pwd = derive(n.ssid)
    if pwd:
        say(c("  │  password ", C.DIM) + c(f"{pwd}", C.GREEN, C.B))
    else:
        say(c("  │  not fh_XXXXXX — manual entry", C.YELLOW))
        pwd = ask("  │  password (or 'q' to skip)")
        if not pwd or pwd.lower() == 'q': 
            say(c("  └──────────────────────────────────────────────", C.DIM))
            return
    say(c("  └──────────────────────────────────────────────", C.DIM))

    ans = ask("  connect now? y/n", "y").lower()
    if ans not in ("y", "yes", ""): return

    ok, msg = connect(n.ssid, pwd)
    if ok:
        say(c(f"  ✓ {msg}", C.GREEN, C.B))
        toast(f"connected: {n.ssid}")
    else:
        say(c(f"  ! {msg}", C.YELLOW))
        toast("manual connect")

def interactive() -> None:
    banner()
    nets, source = scan_all()
    
    if not nets:
        say(c("  no networks via scan.", C.YELLOW))
        say(c("  enter manually below:", C.DIM))
        ssid = ask("SSID (or 'q')")
        if not ssid or ssid.lower() == 'q': return
        do_target(Net(ssid, 0, "?", ""))
        return
        
    while True:
        render(nets, source)
        raw = ask(f"select 1–{len(nets)} (or 'm' manual, 'q' quit)")
        if raw.lower() in ("q", "quit", ""): return
        
        if raw.lower() == "m":
            ssid = ask("SSID")
            if ssid: do_target(Net(ssid, 0, "?", ""))
            continue
            
        try:
            i = int(raw)
            if 1 <= i <= len(nets):
                do_target(nets[i-1])
                say()
                if ask("another? y/n", "n").lower() != "y": return
                nets, source = scan_all() 
        except ValueError:
            say(c("  invalid", C.RED))

def main() -> None:
    ap = argparse.ArgumentParser(prog="fhtx", description="Termux fh_* deriver")
    ap.add_argument("--ssid", help="target SSID non-interactively")
    ap.add_argument("--no-connect", action="store_true", help="derive only")
    ap.add_argument("--list", action="store_true", help="scan and list only")
    args = ap.parse_args()

    global _USE_COLOR
    if not sys.stdout.isatty(): _USE_COLOR = False

    if args.ssid:
        pwd = derive(args.ssid)
        if not pwd:
            say(c(f"{args.ssid} not fh_XXXXXX", C.RED)); sys.exit(1)
        say(f"{args.ssid} → {pwd}")
        if args.no_connect: return
        ok, msg = connect(args.ssid, pwd)
        say(c(("✓ " if ok else "! ") + msg, C.GREEN if ok else C.YELLOW))
        return

    if args.list:
        nets, src = scan_all()
        banner()
        render(nets, src)
        return

    interactive()

if __name__ == "__main__":
    main()