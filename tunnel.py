"""
Temporary public link for Remote-PC via a Cloudflare quick tunnel.

Creates a temporary https://*.trycloudflare.com URL that forwards to the
local server, so you can reach Remote-PC from outside your network without
opening router ports. The link stops working as soon as the tunnel process
exits.

Requires the `cloudflared` binary (https://github.com/cloudflare/cloudflared).
If it is not on PATH, start_tunnel() tries to install it via winget on Windows.
"""

import os
import re
import shutil
import subprocess
import sys
import threading

PUBLIC_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

# Locations checked when `cloudflared` is not on PATH (winget installs it
# here, but a running process does not see PATH updates made by the installer).
_FALLBACK_PATHS = (
    os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "cloudflared", "cloudflared.exe"),
    os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "cloudflared", "cloudflared.exe"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links", "cloudflared.exe"),
)


def find_cloudflared():
    path = shutil.which("cloudflared")
    if path:
        return path
    for candidate in _FALLBACK_PATHS:
        if candidate and os.path.exists(candidate):
            return candidate
    return None


def install_cloudflared():
    winget = shutil.which("winget")
    if not winget:
        return None
    print("cloudflared not found - installing it via winget...")
    subprocess.run(
        [winget, "install", "--id", "Cloudflare.cloudflared", "--exact",
         "--accept-source-agreements", "--accept-package-agreements"],
        check=False,
    )
    return find_cloudflared()


def _watch_for_url(proc, state):
    """Read cloudflared's output until the public URL appears or it dies."""
    try:
        for raw in iter(proc.stderr.readline, b""):
            line = raw.decode("utf-8", errors="replace")
            match = PUBLIC_URL_RE.search(line)
            if match:
                state["url"] = match.group(0)
                break
    except Exception:
        pass
    state["ended"] = True


def start_tunnel(local_port):
    """Start a quick tunnel to http://127.0.0.1:<local_port>.

    Prints the public URL once the tunnel is up. Returns the tunnel process,
    or None if cloudflared could not be obtained.
    """
    exe = find_cloudflared() or install_cloudflared()
    if not exe:
        print("ERROR: cloudflared is required for --tunnel but was not found.")
        print("Install it from https://github.com/cloudflare/cloudflared/releases")
        print("or run: winget install Cloudflare.cloudflared")
        return None

    print("Starting temporary public tunnel (cloudflared)...")
    proc = subprocess.Popen(
        [exe, "tunnel", "--url", f"http://127.0.0.1:{local_port}", "--no-autoupdate"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    state = {}
    watcher = threading.Thread(target=_watch_for_url, args=(proc, state), daemon=True)
    watcher.start()
    watcher.join(timeout=60)

    if proc.poll() is not None:
        print("ERROR: cloudflared exited unexpectedly (code %s)." % proc.returncode)
        return None
    if "url" not in state:
        print("ERROR: timed out waiting for the public tunnel URL.")
        stop_tunnel(proc)
        return None

    url = state["url"]
    print("")
    print("=" * 64)
    print("  TEMPORARY PUBLIC LINK:  %s" % url)
    print("=" * 64)
    print("  Anyone with this link AND your password can control this PC.")
    print("  Set a strong password with the REMOTE_PC_PASSWORD env var.")
    print("  The link stops working when you close Remote-PC.")
    print("")
    return proc


def stop_tunnel(proc):
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
