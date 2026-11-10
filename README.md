# Remote-PC

Browser-based remote access for your own Windows PC. Runs a small FastAPI server locally and lets you view + control your desktop from any browser on the same machine (or LAN, if you change the bind address).

## Quick start

1. Double-click `start.bat` (or run `python server.py` in the folder).
2. Open `http://127.0.0.1:8765` in your browser.
3. Enter the password (default: **admin**).
4. Click the screen to capture input, then move your mouse / type to control the PC.

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
- `static/index.html` — Browser client (screen viewer + input capture)
- `start.bat` — Convenience launcher
