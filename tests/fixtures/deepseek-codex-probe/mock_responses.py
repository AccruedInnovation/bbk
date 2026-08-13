import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

class Handler(BaseHTTPRequestHandler):
    requests = []
    def log_message(self, *_args):
        return
    def do_POST(self):
        n = int(self.headers.get('content-length', '0'))
        body = self.rfile.read(n)
        Handler.requests.append({
            'path': self.path,
            'authorization_present': bool(self.headers.get('authorization')),
            'body': body.decode('utf-8', 'replace'),
        })
        payload = {
            'id': 'resp_probe_1', 'object': 'response', 'status': 'completed',
            'output': [{'type': 'message', 'role': 'assistant', 'content': [
                {'type': 'output_text', 'text': 'probe-ok'}]}],
        }
        raw = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header('content-type', 'application/json')
        self.send_header('content-length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

def main():
    server = HTTPServer(('127.0.0.1', 0), Handler)
    print(server.server_port, flush=True)
    server.timeout = 8
    server.handle_request()
    print(json.dumps(Handler.requests), flush=True)

if __name__ == '__main__':
    main()
