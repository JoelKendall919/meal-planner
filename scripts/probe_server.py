"""Dev-only: serve dist/ and log what the page reports to /probe.

Used to verify service-worker behaviour, because headless Chrome does not exit
cleanly while a service worker is active.
"""

import http.server
import socketserver
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "dist"
LOG = Path("/tmp/probe.log")


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def do_GET(self):
        if self.path.startswith("/probe"):
            query = urllib.parse.urlparse(self.path).query
            msg = urllib.parse.parse_qs(query).get("msg", [""])[0]
            with LOG.open("a") as fh:
                fh.write(msg + "\n")
            self.send_response(204)
            self.end_headers()
            return
        super().do_GET()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    LOG.write_text("")
    with socketserver.TCPServer(("127.0.0.1", 8124), Handler) as srv:
        srv.serve_forever()
