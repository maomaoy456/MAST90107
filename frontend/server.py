"""Serve the local dashboard and proxy API requests without exposing its key."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT.parent / "backend"
sys.path.insert(0, str(BACKEND))

from app.config import Settings  # noqa: E402

HOST = "127.0.0.1"
PORT = int(os.environ.get("DASHBOARD_FRONTEND_PORT", "5173"))
SETTINGS = Settings()
API_BASE = SETTINGS.dashboard_backend_url.rstrip("/") + "/api"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, format, *args):
        pass

    def _proxy(self):
        if SETTINGS.dashboard_api_key is None:
            self.send_error(503, "Dashboard key is not configured")
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else None
        request = Request(API_BASE + self.path.removeprefix("/api"), data=body, method=self.command,
            headers={"X-API-Key": SETTINGS.dashboard_api_key.get_secret_value(),
                     "Content-Type": self.headers.get("Content-Type", "application/json")})
        try:
            response = urlopen(request, timeout=180)
        except HTTPError as error:
            response = error
        except OSError:
            self.send_error(502, "Local API is unavailable")
            return
        payload = response.read()
        self.send_response(response.status)
        self.send_header("Content-Type", response.headers.get("Content-Type", "application/json"))
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        self._proxy() if self.path.startswith("/api/") else super().do_GET()

    def do_POST(self):
        self._proxy() if self.path.startswith("/api/") else self.send_error(405)

    def do_PUT(self):
        self._proxy() if self.path.startswith("/api/") else self.send_error(405)


if __name__ == "__main__":
    print(f"Dashboard available at http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
