"""
Remote-PC desktop app: GUI window + system tray.

Default mode shows a customtkinter window with server controls and a
pystray tray icon; closing the window minimizes to the tray.

Flags:
  --console   Run headless (no window), like `python server.py`
  --tunnel    Start with a temporary public link enabled
"""

import argparse
import json
import logging
import os
import sys
import threading
import webbrowser
from pathlib import Path

import uvicorn

APP_NAME = "Remote-PC"
LOCAL_URL = "http://127.0.0.1:8765"
SETTINGS_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_NAME
SETTINGS_FILE = SETTINGS_DIR / "settings.json"

import customtkinter as ctk
import pystray
from PIL import Image

import server as srv
import tunnel

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def resource_path(*parts: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def load_settings() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(settings: dict) -> None:
    try:
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except Exception as exc:
        print("Failed to save settings:", exc)


def resolve_password(settings: dict) -> str:
    """Env var wins, then settings file, then default."""
    return os.environ.get("REMOTE_PC_PASSWORD") or settings.get("password") or srv.DEFAULT_PASSWORD


class GuiLogHandler(logging.Handler):
    def __init__(self, app: "RemotePcApp"):
        super().__init__()
        self.app = app
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.app.log_line(self.format(record))
        except Exception:
            pass


class RemotePcApp(ctk.CTk):
    def __init__(self, start_tunnel: bool = False):
        super().__init__()
        self.settings = load_settings()
        self.public_url: str | None = None
        self.tunnel_proc = None
        self.tunnel_state: dict | None = None
        self.uvicorn_server: uvicorn.Server | None = None
        self.uvicorn_thread: threading.Thread | None = None

        self.title(APP_NAME)
        self.geometry("500x640")
        self.minsize(460, 560)
        try:
            self.iconbitmap(resource_path("assets", "icon.ico"))
        except Exception:
            pass
        self.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)

        self._build_ui()
        self._attach_uvicorn_logging()
        self._setup_tray()

        self.start_server()
        if start_tunnel:
            self.after(500, self.enable_tunnel)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        pad = {"padx": 16, "pady": 6}

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 4))
        try:
            img = ctk.CTkImage(Image.open(resource_path("assets", "icon.png")), size=(44, 44))
            ctk.CTkLabel(header, image=img, text="").pack(side="left")
        except Exception:
            pass
        ctk.CTkLabel(header, text=APP_NAME, font=ctk.CTkFont(size=22, weight="bold")).pack(side="left", padx=10)
        self.status_label = ctk.CTkLabel(header, text="● stopped", text_color="#f87171", font=ctk.CTkFont(size=13))
        self.status_label.pack(side="right")
        self.top_toggle_button = ctk.CTkButton(
            header,
            text="Start server",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=38,
            width=130,
            command=self.toggle_server,
        )
        self.top_toggle_button.pack(side="right", padx=(0, 12))

        conn = ctk.CTkFrame(self)
        conn.pack(fill="x", **pad)
        ctk.CTkLabel(conn, text="Local address", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=(10, 0))
        row = ctk.CTkFrame(conn, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(4, 10))
        ctk.CTkLabel(row, text=LOCAL_URL, font=ctk.CTkFont(size=15)).pack(side="left")
        ctk.CTkButton(row, text="Open", width=70, command=lambda: webbrowser.open(LOCAL_URL)).pack(side="right", padx=2)
        ctk.CTkButton(row, text="Copy", width=70, command=lambda: self.copy_text(LOCAL_URL)).pack(side="right", padx=2)

        pw = ctk.CTkFrame(self)
        pw.pack(fill="x", **pad)
        ctk.CTkLabel(pw, text="Password", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=(10, 0))
        row = ctk.CTkFrame(pw, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(4, 6))
        self.password_var = ctk.StringVar(value=resolve_password(self.settings))
        entry = ctk.CTkEntry(row, textvariable=self.password_var, show="•", width=200)
        entry.pack(side="left")
        ctk.CTkButton(row, text="Save", width=70, command=self.save_password).pack(side="left", padx=8)
        hint = (
            "Saved to settings. Restarting server to apply."
            if not os.environ.get("REMOTE_PC_PASSWORD")
            else "REMOTE_PC_PASSWORD env var overrides this."
        )
        ctk.CTkLabel(pw, text=hint, text_color="#94a3b8", font=ctk.CTkFont(size=11)).pack(anchor="w", padx=12, pady=(0, 10))

        pub = ctk.CTkFrame(self)
        pub.pack(fill="x", **pad)
        ctk.CTkLabel(pub, text="Temporary public link (internet access)", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=12, pady=(10, 0)
        )
        self.tunnel_button = ctk.CTkButton(pub, text="Enable public link", command=self.enable_tunnel)
        self.tunnel_button.pack(anchor="w", padx=12, pady=(8, 4))
        self.tunnel_row = ctk.CTkFrame(pub, fg_color="transparent")
        self.tunnel_link_var = ctk.StringVar(value="")
        link_entry = ctk.CTkEntry(self.tunnel_row, textvariable=self.tunnel_link_var, width=320)
        link_entry.pack(side="left")
        ctk.CTkButton(self.tunnel_row, text="Copy", width=70, command=lambda: self.copy_text(self.public_url or "")).pack(
            side="left", padx=8
        )
        ctk.CTkLabel(
            pub,
            text="Anyone with the link and your password can control this PC. The link stops working when you quit.",
            text_color="#94a3b8",
            font=ctk.CTkFont(size=11),
            wraplength=440,
            justify="left",
        ).pack(anchor="w", padx=12, pady=(2, 10))

        opts = ctk.CTkFrame(self, fg_color="transparent")
        opts.pack(fill="x", padx=20)
        self.auto_open_var = ctk.BooleanVar(value=bool(self.settings.get("auto_open", True)))
        ctk.CTkCheckBox(opts, text="Open in browser when the server starts", variable=self.auto_open_var,
                        command=self.save_auto_open).pack(anchor="w")

        ctk.CTkLabel(self, text="Log", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20, pady=(10, 0))
        self.log_box = ctk.CTkTextbox(self, height=150, font=ctk.CTkFont(size=12))
        self.log_box.pack(fill="both", expand=True, padx=16, pady=(4, 8))
        self.log_box.configure(state="disabled")

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=16, pady=(0, 12))
        self.start_stop_button = ctk.CTkButton(actions, text="Stop server", fg_color="#b91c1c", hover_color="#7f1d1d",
                                               command=self.toggle_server)
        self.start_stop_button.pack(side="left")
        ctk.CTkButton(actions, text="Quit", fg_color="#334155", hover_color="#1e293b",
                      command=self.quit_app).pack(side="right")

    # ------------------------------------------------------------------ log
    def log_line(self, message: str) -> None:
        def append():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", message + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after_idle(append)

    def _attach_uvicorn_logging(self) -> None:
        handler = GuiLogHandler(self)
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
            logger = logging.getLogger(name)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)

    # --------------------------------------------------------------- server
    def start_server(self) -> None:
        if self.uvicorn_server is not None:
            return
        password = resolve_password(self.settings)
        config = uvicorn.Config(srv.create_app(password), host=srv.HOST, port=srv.PORT, log_config=None)
        self.uvicorn_server = uvicorn.Server(config)
        self.uvicorn_thread = threading.Thread(target=self._run_server, daemon=True)
        self.uvicorn_thread.start()
        self.log_line(f"Server starting at {LOCAL_URL}")
        self._poll_server_state()

    def _run_server(self) -> None:
        try:
            self.uvicorn_server.run()
        except Exception as exc:
            self.log_line(f"Server error: {exc}")
        finally:
            self.uvicorn_server = None

    def _poll_server_state(self) -> None:
        srv_inst = self.uvicorn_server
        running = srv_inst is not None and srv_inst.started
        if running:
            self.status_label.configure(text="● running", text_color="#34d399")
            for btn in (self.start_stop_button, self.top_toggle_button):
                btn.configure(text="Stop server", fg_color="#b91c1c", hover_color="#7f1d1d")
            if self.auto_open_var.get() and not getattr(self, "_opened_once", False):
                self._opened_once = True
                webbrowser.open(LOCAL_URL)
        else:
            self.status_label.configure(text="● stopped", text_color="#f87171")
            for btn in (self.start_stop_button, self.top_toggle_button):
                btn.configure(text="Start server", fg_color="#1f6aa5", hover_color="#144870")
        self.after(500, self._poll_server_state)

    def stop_server(self) -> None:
        if self.uvicorn_server is not None:
            self.log_line("Stopping server…")
            self.uvicorn_server.should_exit = True
            self._opened_once = False

    def toggle_server(self) -> None:
        if self.uvicorn_server is not None:
            self.stop_server()
        else:
            self.start_server()

    # -------------------------------------------------------------- settings
    def save_password(self) -> None:
        pw = self.password_var.get().strip()
        self.settings["password"] = pw
        save_settings(self.settings)
        self.log_line("Password saved.")
        if self.uvicorn_server is not None:
            self.log_line("Restarting server to apply the new password…")
            self.stop_server()
            self.after(1200, self.start_server)

    def save_auto_open(self) -> None:
        self.settings["auto_open"] = bool(self.auto_open_var.get())
        save_settings(self.settings)

    # --------------------------------------------------------------- tunnel
    def enable_tunnel(self) -> None:
        if self.tunnel_proc is not None:
            return
        self.log_line("Starting temporary public tunnel…")
        proc, state = tunnel.start_tunnel_process(srv.PORT)
        if proc is None:
            self.log_line("cloudflared not found. Install it: winget install Cloudflare.cloudflared")
            return
        self.tunnel_proc, self.tunnel_state = proc, state
        self.tunnel_button.configure(text="Disable public link", fg_color="#b91c1c", hover_color="#7f1d1d",
                                     command=self.disable_tunnel)
        self._poll_tunnel_state()

    def _poll_tunnel_state(self) -> None:
        if self.tunnel_proc is None:
            return
        if self.tunnel_proc.poll() is not None:
            self.log_line("Tunnel process exited.")
            self._clear_tunnel_ui()
            return
        url = (self.tunnel_state or {}).get("url")
        if url:
            if url != self.public_url:
                self.public_url = url
                self.tunnel_link_var.set(url)
                self.tunnel_row.pack(after=self.tunnel_button, anchor="w", padx=12, pady=(0, 4))
                self.log_line(f"Public link ready: {url}")
        self.after(500, self._poll_tunnel_state)

    def disable_tunnel(self) -> None:
        if self.tunnel_proc is not None:
            tunnel.stop_tunnel(self.tunnel_proc)
        self.log_line("Public link stopped.")
        self._clear_tunnel_ui()

    def _clear_tunnel_ui(self) -> None:
        self.tunnel_proc = None
        self.tunnel_state = None
        self.public_url = None
        self.tunnel_link_var.set("")
        self.tunnel_row.pack_forget()
        self.tunnel_button.configure(text="Enable public link", fg_color="#1f6aa5", hover_color="#144870",
                                     command=self.enable_tunnel)

    # ------------------------------------------------------------------ tray
    def _setup_tray(self) -> None:
        try:
            image = Image.open(resource_path("assets", "icon.png"))
        except Exception:
            image = Image.new("RGB", (64, 64), "#0b0c10")
        menu = pystray.Menu(
            pystray.MenuItem("Open " + APP_NAME, lambda: self.after(0, self.show_window)),
            pystray.MenuItem(self._tray_toggle_text, lambda: self.after(0, self.toggle_server)),
            pystray.MenuItem("Open in browser", lambda: webbrowser.open(self.public_url or LOCAL_URL)),
            pystray.MenuItem(
                "Copy public link",
                lambda: self.copy_text(self.public_url or ""),
                enabled=lambda item: self.public_url is not None,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda: self.after(0, self._quit_from_main)),
        )
        self.tray_icon = pystray.Icon("remote-pc", image, APP_NAME, menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _tray_toggle_text(self, item) -> str:
        srv_inst = self.uvicorn_server
        return "Stop server" if (srv_inst is not None and srv_inst.started) else "Start server"

    def minimize_to_tray(self) -> None:
        self.withdraw()

    def show_window(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()

    # ------------------------------------------------------------------ misc
    def copy_text(self, text: str) -> None:
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.log_line("Copied to clipboard.")

    def quit_app(self) -> None:
        # UI button path: we are already on the main thread.
        self._quit_from_main()

    def _quit_from_main(self) -> None:
        try:
            if self.tunnel_proc is not None:
                tunnel.stop_tunnel(self.tunnel_proc)
            if self.uvicorn_server is not None:
                self.uvicorn_server.should_exit = True
            if self.tray_icon is not None:
                self.tray_icon.stop()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Remote-PC")
    parser.add_argument("--console", action="store_true", help="Run headless without the GUI")
    parser.add_argument("--tunnel", action="store_true", help="Start with the public link enabled")
    args = parser.parse_args()

    if args.console:
        sys.argv = [sys.argv[0]] + (["--tunnel"] if args.tunnel else [])
        srv.console_main()
        return

    app = RemotePcApp(start_tunnel=args.tunnel)
    app.mainloop()


if __name__ == "__main__":
    main()
