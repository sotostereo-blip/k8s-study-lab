"""Alertmanager webhook receiver for the lab.

POST <any path>   stores the JSON body together with the path (for example /payments)
GET  /alerts      every notification received: [{"path": "/payments", "received": 1700000000, "body": {...}}]
GET  /healthz     200 when the server is running
"""
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

NOTIFICATIONS = []


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            body = {"raw": raw.decode(errors="replace")}
        NOTIFICATIONS.append({"path": self.path, "received": int(time.time()), "body": body})
        del NOTIFICATIONS[:-500]
        names = [a.get("labels", {}).get("alertname") for a in body.get("alerts", [])] if isinstance(body, dict) else []
        print(f"{self.path}: {body.get('status') if isinstance(body, dict) else '?'} {names}", flush=True)
        self._send(200, {"ok": True})

    def do_GET(self):
        if self.path.startswith("/alerts"):
            self._send(200, NOTIFICATIONS)
        elif self.path.startswith("/healthz"):
            self._send(200, {"ok": True})
        else:
            self._send(404, {"error": "use GET /alerts"})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print("webhook receiver on :9000 (GET /alerts lists notifications)", flush=True)
    ThreadingHTTPServer(("", 9000), Handler).serve_forever()
