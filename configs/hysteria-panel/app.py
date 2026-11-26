#!/usr/bin/env python3
"""
Lightweight Hysteria 2 Auth Webhook & User Management Panel
Listens on http://127.0.0.1:2054
Accepts both legacy single token and username:password credentials.
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os

USERS_FILE = os.environ.get("USERS_FILE", "/etc/hysteria/users.json")

def load_users():
    if not os.path.exists(USERS_FILE):
        return {"users": {}}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"users": {}}

class AuthHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/auth":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                auth_str = data.get("auth", "")
                client_addr = data.get("addr", "")
                
                users_data = load_users()
                users = users_data.get("users", {})
                
                # Check legacy token or username:password
                authenticated = False
                matched_user = "unknown"
                
                if ":" in auth_str:
                    username, password = auth_str.split(":", 1)
                    if username in users and users[username].get("password") == password:
                        authenticated = True
                        matched_user = username
                else:
                    for u, cfg in users.items():
                        if cfg.get("password") == auth_str:
                            authenticated = True
                            matched_user = u
                            break
                
                if authenticated:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": True, "id": matched_user}).encode())
                else:
                    self.send_response(401)
                    self.end_headers()
            except Exception:
                self.send_response(400)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "running"}).encode())
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 2054), AuthHandler)
    print("Hysteria Auth Service listening on 127.0.0.1:2054")
    server.serve_forever()
