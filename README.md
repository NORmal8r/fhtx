# fhtx — Termux Wi-Fi Default Password Deriver

A Termux-native Python tool designed to derive default WLAN passwords for routers with the `fh_XXXXXX` SSID pattern, scan nearby networks, and automate the connection process.

> ⚠️ **Educational Purposes Only**
> This tool is strictly for educational and security auditing purposes. Do not use it against any network you do not own or have explicit permission to test. Test it on your own router, change the default password, and secure your network.

## Features
- **Auto-scan**: Scans nearby networks (requires Root, ADB, or Termux:API).
- **Password Derivation**: Automatically calculates the default password based on the SSID suffix.
- **Auto-connect**: Connects to the network (requires Root or Wireless ADB). Falls back to copying the password to the clipboard and opening Wi-Fi settings for non-root users.
- **Zero dependencies**: Uses Python standard library only.

## Installation (Termux)
```bash
pkg update && pkg upgrade
pkg install python git
# Optional for non-root scanning:
pkg install termux-api
git clone https://github.com/NORmal8r/fhtx.git
# run
cd fhtx
python fhtx.py
