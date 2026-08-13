"""Loopback-only OpenAI Responses-compatible mock for WU-DS-01C.

The server binds to 127.0.0.1 only and emits a single request receipt with
authorization values redacted. It is qualification apparatus, not product code.
"""
from __future__ import annotations

import json
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    requests: list[dict[str, object]] = []

    def log_message(self, *_args: object) -> None:
        return

    def do_POST(self) -> None:  # noqa: N802 - stdlib hook name
        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length)
        Handler.requests.append(
            {
                "path": self.path,
                "method": "POST",
                "authorization_present": bool(self.headers.get("authorization")),
                "content_type": self.headers.get("content-type"),
                "body_sha256": __import__("hashlib").sha256(body).hexdigest(),
                "body_bytes": len(body),
                "probe_marker": (re.search(rb"WU-DS-01C-R2-[A-Za-z0-9-]+", body) or [b""])[0].decode("ascii", "ignore"),
            }
        )
        if self.path.startswith("/api/chat"):
            payload = {"message": {"role": "assistant", "content": "probe-ok"}, "done": True}
        else:
            payload = {
            "id": "resp_wu_ds_01c_1",
            "object": "response",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "probe-ok"}],
                }
            ],
            }
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802 - stdlib hook name
        Handler.requests.append({"path": self.path, "method": "GET"})
        if self.path == "/":
            raw = b"Ollama is running"
            self.send_response(200)
            self.send_header("content-type", "text/plain")
            self.send_header("content-length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        elif self.path.startswith("/api/tags"):
            payload = {"models": [{"name": "deepseek-v4-flash"}]}
            raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        else:
            raw = b'{"version":"0.0.0"}'
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)


def main() -> None:
    requested_port = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    server = HTTPServer(("127.0.0.1", requested_port), Handler)
    print(server.server_port, flush=True)
    server.timeout = 12
    for _ in range(5):
        server.handle_request()
        if any(item.get("method") == "POST" for item in Handler.requests):
            break
    print(json.dumps(Handler.requests, sort_keys=True), flush=True)
    server.server_close()


if __name__ == "__main__":
    main()
