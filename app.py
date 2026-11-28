"""Spyro Recomp Trilogy – launcher and setup for the native PC ports.

    python app.py            normal window (pywebview / WebView2)
    python app.py --serve    developer mode: UI on http://127.0.0.1:8765
"""
from __future__ import annotations

import json
import mimetypes
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from backend.api import Api
from backend import tools

UI_DIR = tools.app_dir() / "ui"


def serve(port: int = 8765) -> None:
    api = Api()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/":
                path = "/index.html"
            f = (UI_DIR / path.lstrip("/")).resolve()
            if not str(f).startswith(str(UI_DIR.resolve())) or not f.is_file():
                self.send_error(404)
                return
            data = f.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(str(f))[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            if not self.path.startswith("/api/"):
                self.send_error(404)
                return
            name = self.path[5:]
            n = int(self.headers.get("Content-Length") or 0)
            args = json.loads(self.rfile.read(n) or b"[]")
            fn = getattr(api, name, None)
            if fn is None or name.startswith("_"):
                self.send_error(404)
                return
            try:
                result = {"ok": True, "result": fn(*args)}
            except Exception as e:  # noqa: BLE001
                result = {"ok": False, "error": str(e)}
            data = json.dumps(result).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Spyro Recomp Trilogy UI: http://127.0.0.1:{port}", flush=True)
    srv.serve_forever()


def unblock_own_files() -> None:
    """Remove the "downloaded from the internet" mark from the app's own files.

    Windows Explorer copies this mark (the Zone.Identifier stream) from a
    downloaded ZIP to every extracted file, and .NET then refuses to load
    Python.Runtime.dll, so the window could not open. Only touches files
    inside the app's own folder; errors are ignored.
    """
    if not (tools.IS_WINDOWS and getattr(sys, "frozen", False)):
        return
    root = Path(sys.executable).parent
    for folder, _dirs, files in os.walk(root):
        for name in files:
            try:
                os.remove(os.path.join(folder, name) + ":Zone.Identifier")
            except OSError:
                pass


def main() -> None:
    if "--serve" in sys.argv:
        serve()
        return
    unblock_own_files()
    import webview
    api = Api()
    window = webview.create_window(
        "Spyro Recomp Trilogy", str(UI_DIR / "index.html"), js_api=api,
        width=1280, height=800, min_size=(1024, 680), background_color="#120a24")
    api._window = window
    webview.start(gui="edgechromium" if tools.IS_WINDOWS else None, debug="--debug" in sys.argv)


if __name__ == "__main__":
    main()
