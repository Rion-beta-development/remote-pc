# Remote-PC

Browser-based remote access for your own Windows PC. Runs a small FastAPI server locally and lets you view + control your desktop from any browser on the same machine (or LAN, if you change the bind address).

## Download

Get the latest release from the [Releases page](https://github.com/Rion-beta-development/remote-pc/releases):

- **`Remote-PC-Setup-1.1.0.exe`** — Installer. Downloads, runs the setup wizard, and adds Remote-PC to your Start Menu. Recommended.
- **`Remote-PC-1.1.0-portable.exe`** — Portable single exe. No installation; just run it.

Then launch Remote-PC and open `http://127.0.0.1:8765` in your browser. The default password is **admin** — change it by setting the `REMOTE_PC_PASSWORD` environment variable before launching (see below).

## Quick start (from source)

1. Double-click `start.bat` (or run `python server.py` in the folder).
2. Open `http://127.0.0.1:8765` in your browser.
3. Enter the password (default: **admin**).
4. Click the screen to capture input, then move your mouse / type to control the PC.

## Access from the internet (temporary public link)

Run with `--tunnel` to get a **temporary public HTTPS link** (via a [Cloudflare quick tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/)) — no router config, no account needed:

- **From source:** double-click `start-tunnel.bat` (or run `python server.py --tunnel`).
- **Installed:** launch **Remote-PC (Public Link)** from the Start Menu.

The console prints a `https://…trycloudflare.com` link that works from any browser, anywhere. The link dies when you close Remote-PC (Ctrl+C or close the window).

This requires the free `cloudflared` binary — on Windows it is installed automatically via `winget` the first time you use `--tunnel`; otherwise install it manually from [cloudflare/cloudflared](https://github.com/cloudflare/cloudflared/releases).

> ⚠️ **Anyone with the link and your password can fully control your PC over the internet.** Always set a strong password first:
> ```
> set REMOTE_PC_PASSWORD=your-strong-password
> ```
> Traffic between the browser and Cloudflare is HTTPS; the last hop (Cloudflare → your PC) is plain HTTP on localhost.

## Stop the server

To stop Remote-PC:

- **From `start.bat`:** Press `Ctrl+C` in the terminal window, or close the window.
- **From `python server.py`:** Press `Ctrl+C` in the terminal.
- **From Task Manager:** End any `python.exe` process running `server.py`.
- **Force kill (all Python processes):** Open PowerShell and run:
  ```powershell
  Get-Process python | Where-Object { $_.MainWindowTitle -like '*server*' } | Stop-Process
  ```
  Or from Command Prompt:
  ```cmd
  taskkill /F /IM python.exe
  ```

After stopping, the server will no longer be reachable at `http://127.0.0.1:8765`. Restart it with `start.bat` when you need it again.

## Change the password

Set the environment variable before launching:

```
set REMOTE_PC_PASSWORD=your-strong-password
start.bat
```

## How it works

- `server.py` captures your screen with `mss`, compresses to JPEG, and streams frames over a WebSocket.
- The browser client (`static/index.html`) displays the stream and captures mouse/keyboard events, sending them back over WebSocket.
- `pynput` injects the input locally on your machine.
- The server binds to `127.0.0.1` (localhost) by default — only your own PC can reach it.

## Security warnings

⚠️ This is a **personal prototype**, not hardened remote-access software.

- **Do not expose port 8765 to the internet.** If you need access from outside your LAN, use a VPN (Tailscale, WireGuard, etc.) or an SSH tunnel — never open the raw port.
- The default password is `admin`. Change it with `REMOTE_PC_PASSWORD`.
- Traffic between browser and server is plain HTTP/WS (no TLS). On localhost this is fine; across a LAN it is sniffable.
- Anyone who can reach `http://<your-pc>:8765` and knows the password can control your mouse and keyboard.

## Files

- `server.py` — FastAPI server (screen capture + WebSocket + input injection)
- `tunnel.py` — Temporary public link via Cloudflare quick tunnel (`--tunnel`)
- `static/index.html` — Browser client (screen viewer + input capture)
- `start.bat` — Convenience launcher
- `start-tunnel.bat` — Launcher with a temporary public link (`--tunnel`)
- `installer/Remote-PC.iss` — Inno Setup script used to build the Windows installer
- `assets/` — App icon (PNG + ICO)

## Build from source

Requires Python 3.11+.

1. Install dependencies: `pip install pyinstaller fastapi "uvicorn[standard]" mss pillow pynput`
2. Build the exe (from the repo root):
   ```
   python -m PyInstaller --onefile --name remote-pc --icon assets/icon.ico --add-data "static;static" server.py
   ```
3. (Optional) Build the installer with [Inno Setup 6](https://jrsoftware.org/isinfo.php): compile `installer/Remote-PC.iss`.
