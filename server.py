"""
Remote-PC: Browser-based remote access tool for your own computer.

Runs a FastAPI server on localhost that:
  - Captures your screen and streams it as JPEG frames over WebSocket
  - Receives mouse/keyboard commands from the browser and injects them locally
  - Requires a password (default: "admin") before allowing control

SECURITY NOTES:
  * Binds to 127.0.0.1 (localhost) by default — only your own PC can reach it.
  * Do NOT expose this to the internet without a VPN / tunnel + strong auth.
  * This is a personal-tool prototype, not enterprise-grade remote access software.
"""

import argparse
import asyncio
import base64
import io
import json
import os
import sys
import threading
import time
from typing import Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from mss import mss
from PIL import Image

from pynput.mouse import Controller as MouseController, Button
from pynput.keyboard import Controller as KeyboardController, Key

import tunnel

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
HOST = "127.0.0.1"          # localhost only by default
PORT = 8765
QUALITY = 70                 # JPEG quality (1-100)
MAX_WIDTH = 1920             # downscale cap to keep bandwidth sane
FPS_TARGET = 15              # target capture frame rate

DEFAULT_PASSWORD = "admin"


def effective_password() -> str:
    """Password: REMOTE_PC_PASSWORD env var wins, else default."""
    return os.environ.get("REMOTE_PC_PASSWORD", DEFAULT_PASSWORD)

# ---------------------------------------------------------------------------
# Input controllers (run on the local machine)
# ---------------------------------------------------------------------------
mouse = MouseController()
keyboard = KeyboardController()

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


class AuthRequest(BaseModel):
    password: str


def create_app(password: str) -> FastAPI:
    app = FastAPI(title="Remote-PC")
    app.state.password = password
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    def verify_password(candidate: str) -> bool:
        return candidate == password

    # -----------------------------------------------------------------------
    # Routes
    # -----------------------------------------------------------------------
    @app.get("/")
    async def index():
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))

    @app.post("/auth")
    async def auth(req: AuthRequest):
        if not verify_password(req.password):
            raise HTTPException(status_code=401, detail="Invalid password")
        return {"ok": True}

    @app.get("/screen-info")
    async def screen_info():
        """Return monitor dimensions so the client can size the viewer."""
        with mss() as sct:
            mon = sct.monitors[0]  # all monitors combined
            return {
                "width": mon["width"],
                "height": mon["height"],
                "left": mon["left"],
                "top": mon["top"],
            }

    # -----------------------------------------------------------------------
    # WebSocket: screen streaming + input commands
    # -----------------------------------------------------------------------
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = Query(None)):
        # Simple token check on connect
        if not token or not verify_password(token):
            await websocket.close(code=4401, reason="Unauthorized")
            return
    
        await websocket.accept()
    
        # Nested coroutines so they share this websocket + close cleanly together
        async def send_screen():
            """Capture screen and push JPEG frames to the browser."""
            try:
                with mss() as sct:
                    monitor = sct.monitors[0]
                    interval = 1.0 / FPS_TARGET
                    while True:
                        start = time.time()
    
                        # Grab the full virtual screen
                        img = sct.grab(monitor)
    
                        # Convert to PIL, optionally downscale
                        pil = Image.frombytes("RGB", img.size, img.rgb)
                        if pil.width > MAX_WIDTH:
                            ratio = MAX_WIDTH / pil.width
                            new_h = int(pil.height * ratio)
                            pil = pil.resize((MAX_WIDTH, new_h), Image.LANCZOS)
    
                        buf = io.BytesIO()
                        pil.save(buf, format="JPEG", quality=QUALITY, optimize=True)
                        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    
                        await websocket.send_text(
                            json.dumps({"type": "frame", "data": b64})
                        )
    
                        # Throttle to target FPS
                        elapsed = time.time() - start
                        await asyncio.sleep(max(0, interval - elapsed))
            except (WebSocketDisconnect, Exception):
                pass
    
        async def recv_commands():
            """Receive mouse/keyboard commands from the browser and inject them."""
            try:
                while True:
                    raw = await websocket.receive_text()
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
    
                    mtype = msg.get("type")
    
                    if mtype == "mousemove":
                        x = int(msg.get("x", 0))
                        y = int(msg.get("y", 0))
                        mouse.position = (x, y)
    
                    elif mtype == "mousedown":
                        btn = msg.get("button", "left")
                        b = Button.left if btn == "left" else Button.right if btn == "right" else Button.middle
                        mouse.press(b)
    
                    elif mtype == "mouseup":
                        btn = msg.get("button", "left")
                        b = Button.left if btn == "left" else Button.right if btn == "right" else Button.middle
                        mouse.release(b)
    
                    elif mtype == "mousescroll":
                        dx = int(msg.get("dx", 0))
                        dy = int(msg.get("dy", 0))
                        mouse.scroll(dx, dy)
    
                    elif mtype == "keydown":
                        key_name = msg.get("key", "")
                        _press_key(key_name)
    
                    elif mtype == "keyup":
                        key_name = msg.get("key", "")
                        _release_key(key_name)
    
                    elif mtype == "type":
                        text = msg.get("text", "")
                        keyboard.type(text)
    
                    elif mtype == "hotkey":
                        keys = msg.get("keys", [])
                        _press_hotkey(keys)
    
                    elif mtype == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))
            except (WebSocketDisconnect, Exception):
                pass
    
        # Tasks: one sends screen frames, one receives input commands
        send_task = asyncio.create_task(send_screen())
        recv_task = asyncio.create_task(recv_commands())
    
        # Run until one side disconnects
        try:
            await asyncio.wait([send_task, recv_task], return_when=asyncio.FIRST_COMPLETED)
        finally:
            for t in (send_task, recv_task):
                t.cancel()

    return app


def _press_key(name: str):
    try:
        k = _parse_key(name)
        keyboard.press(k)
    except Exception:
        pass


def _release_key(name: str):
    try:
        k = _parse_key(name)
        keyboard.release(k)
    except Exception:
        pass


def _parse_key(name: str):
    """Map common key names to pynput Key objects or return the raw char."""
    special = {
        "enter": Key.enter,
        "return": Key.enter,
        "tab": Key.tab,
        "shift": Key.shift,
        "ctrl": Key.ctrl,
        "control": Key.ctrl,
        "alt": Key.alt,
        "esc": Key.esc,
        "escape": Key.esc,
        "space": Key.space,
        "backspace": Key.backspace,
        "delete": Key.delete,
        "up": Key.up,
        "down": Key.down,
        "left": Key.left,
        "right": Key.right,
        "home": Key.home,
        "end": Key.end,
        "pageup": Key.page_up,
        "pagedown": Key.page_down,
        "f1": Key.f1, "f2": Key.f2, "f3": Key.f3, "f4": Key.f4,
        "f5": Key.f5, "f6": Key.f6, "f7": Key.f7, "f8": Key.f8,
        "f9": Key.f9, "f10": Key.f10, "f11": Key.f11, "f12": Key.f12,
        "cmd": Key.cmd, "win": Key.cmd,
        "capslock": Key.caps_lock,
        "numlock": Key.num_lock,
    }
    n = name.lower().strip()
    if n in special:
        return special[n]
    return name  # pynput accepts single chars


def _press_hotkey(keys):
    """Press a list of keys together (e.g. ['ctrl','c'])."""
    parsed = [_parse_key(k) for k in keys]
    for k in parsed:
        keyboard.press(k)
    for k in reversed(parsed):
        keyboard.release(k)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
def console_main():
    parser = argparse.ArgumentParser(description="Remote-PC server")
    parser.add_argument(
        "--tunnel",
        action="store_true",
        help="Create a temporary public HTTPS link via a Cloudflare quick tunnel",
    )
    args = parser.parse_args()

    password = effective_password()
    print(f"Remote-PC server starting on http://{HOST}:{PORT}")
    print(f"Password: {password}")
    print("Open http://127.0.0.1:8765 in your browser and enter the password.")

    tunnel_proc = None
    if args.tunnel:
        tunnel_proc = tunnel.start_tunnel(PORT)
        if tunnel_proc is None:
            sys.exit(1)

    try:
        uvicorn.run(create_app(password), host=HOST, port=PORT)
    finally:
        if tunnel_proc is not None:
            tunnel.stop_tunnel(tunnel_proc)


if __name__ == "__main__":
    console_main()
