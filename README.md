# Remote-PC

Browser-based remote access for your own Windows PC — now with a desktop app and a modern web client.

Remote-PC runs a small FastAPI server on your machine and lets you view + control your desktop from any browser — on the same computer, on your LAN, or anywhere on the internet via a temporary public link.

## Download

Get the latest release from the [Releases page](https://github.com/Rion-beta-development/remote-pc/releases):

- **`Remote-PC-Setup-2.2.0.exe`** — Installer. Adds Remote-PC to your Start Menu. Recommended.
- **`Remote-PC-2.2.0-portable.exe`** — Portable single exe. No installation; just run it.

No Python required — both are standalone builds.

## The desktop app

The app opens a control window:

- **Start/Stop** the server with one button
- **Open** the local address (`http://127.0.0.1:8765`) or copy it
- **Set a password** — saved to `%APPDATA%\Remote-PC\settings.json` (the `REMOTE_PC_PASSWORD` env var still overrides it)
- **Temporary public link** — one click creates a `https://…trycloudflare.com` URL for internet access, with a Copy button
- **Auto-open** the browser when the server starts
- A **log** of server activity

Closing the window does not stop the server — the app keeps running in the **system tray** (near the clock). From the tray menu you can reopen the window, open the web UI, copy the public link, or quit (which stops everything).

## The web client

Modern dark UI, served by the app:

- Branded login screen with show-password and **clear error messages** (wrong password vs. server unreachable)
- Smooth screen streaming with FPS and scale readouts
- **Fit / zoom** modes and fullscreen
- **Click to take control**, with an on/off toggle for input
- **Ctrl+V paste** — clipboard text is typed on the remote PC
- **Task Manager** button (Ctrl+Shift+Esc — honest replacement for Ctrl+Alt+Del, which Windows does not allow software to send)
- Automatic reconnect with backoff when the connection drops

## Access from the internet (temporary public link)

In the desktop app, click **Enable public link**. It creates a **temporary HTTPS link** via a [Cloudflare quick tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/) — no router config, no account needed. The link stops working when you disable it or quit the app.

This requires the free `cloudflared` binary — on Windows it is installed automatically via `winget` the first time you enable the link; otherwise install it from [cloudflare/cloudflared](https://github.com/cloudflare/cloudflared/releases).

From the command line (source or portable exe), `--tunnel` does the same:

```
python server.py --tunnel
remote-pc.exe --tunnel
```

> ⚠️ **Anyone with the link and your password can fully control your PC.** Set a strong password in the app before enabling the public link.

## Command-line flags

| Flag | Effect |
|---|---|
| *(no flags)* | Desktop app (window + system tray) |
| `--tunnel` | Desktop app, with the public link enabled at startup |
| `--console` | Headless server, no window (like the old behavior) |

## How it works

- `app.py` — desktop app (customtkinter window + pystray tray); runs the server in a background thread
- `server.py` — FastAPI server (screen capture + WebSocket + input injection)
- `tunnel.py` — temporary public link via Cloudflare quick tunnel
- `client/` — web client source (Vite + React + TypeScript + Tailwind); builds into `static/`
- `static/` — built web client, served by the server
- `installer/Remote-PC.iss` — Inno Setup script for the Windows installer

## Security notes

⚠️ This is a **personal tool**, not hardened remote-access software.

- The server binds to `127.0.0.1` (localhost) by default — only your own PC can reach it.
- **Do not expose port 8765 directly to the internet.** Use the built-in public link or a VPN (Tailscale, WireGuard) instead.
- Traffic between browser and server is plain HTTP/WS on localhost (fine) — the Cloudflare public link adds HTTPS end-to-end from the browser.
- Anyone who can reach the server and knows the password can control your mouse and keyboard.

## Build from source

Requires Python 3.11+ and Node.js.

1. Server/app dependencies: `pip install fastapi "uvicorn[standard]" mss pillow pynput customtkinter pystray`
2. Web client (from `client/`): `npm install && npm run build` — output lands in `static/`
3. Desktop exe (from repo root):
   ```
   python -m PyInstaller --onefile --windowed --name remote-pc --icon assets/icon.ico --add-data "static;static" --add-data "assets;assets" app.py
   ```
4. (Optional) Installer with [Inno Setup 6](https://jrsoftware.org/isinfo.php): compile `installer/Remote-PC.iss`

## Development

- Run the server: `python server.py` (console) or `python app.py` (GUI)
- Client dev server with hot reload (from `client/`): `npm run dev` — proxies API/WebSocket calls to `localhost:8765`
