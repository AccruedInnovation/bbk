"""Attempt-local loopback Responses mock for WU-DS-01C@3."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    requests: list[dict[str, object]] = []

    def log_message(self, *_args: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        Handler.requests.append({"method": "GET", "path": self.path})
        payload = {"data": [{"id": "deepseek-v4-flash", "object": "model"}]} if self.path.endswith("/v1/models") else {"version": "0.0.0"}
        raw = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length)
        marker = re.search(rb"WU-DS-01C-R4-[A-Za-z0-9-]+", body)
        Handler.requests.append({
            "method": "POST", "path": self.path,
            "authorization_present": bool(self.headers.get("authorization")),
            "content_type": self.headers.get("content-type"),
            "body_bytes": len(body), "body_sha256": hashlib.sha256(body).hexdigest(),
            "probe_marker": marker.group(0).decode() if marker else "",
        })
        if self.path == "/api/pull":
            raw = b'{"status":"success"}\n'
        else:
            raw = json.dumps({"id": "resp_wu_ds_01c_r4", "object": "response", "status": "completed", "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "probe-ok"}]}]}, separators=(",", ":")).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def main() -> None:
    server = HTTPServer(("127.0.0.1", int(sys.argv[1]) if len(sys.argv) > 1 else 11434), Handler)
    print(server.server_port, flush=True)
    server.timeout = 10
    for _ in range(12):
        server.handle_request()
        if any(x.get("method") == "POST" and x.get("path") == "/v1/responses" for x in Handler.requests):
            break
    print(json.dumps(Handler.requests, sort_keys=True), flush=True)
    server.server_close()


if __name__ == "__main__":
    main()
