from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class NoBackendHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = json.dumps({"error": "synthetic smoke backend has no data"}).encode()
        self.send_response(503)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        self.do_GET()

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    endpoint_file = Path(sys.argv[1])
    server = ThreadingHTTPServer(("127.0.0.1", 0), NoBackendHandler)
    endpoint_file.write_text(f"{server.server_port}\n")
    server.serve_forever()


if __name__ == "__main__":
    main()
