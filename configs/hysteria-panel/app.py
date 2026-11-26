#!/usr/bin/env python3
"""
Lightweight Hysteria 2 Auth Webhook & Web Management Dashboard
- Auth webhook: POST http://127.0.0.1:2054/api/auth (supports both user:pass and legacy password-only)
- Health check: GET  http://127.0.0.1:2054/health
- Web UI:       GET  http://<VPS_IP>:2054/ (protected by HTTP Basic Auth)
"""
import base64
import json
import os
import secrets
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

PORT = int(os.environ.get("HY_PANEL_PORT", "2054"))
USERS_FILE = os.environ.get("USERS_FILE", "/opt/hysteria-panel/users.json")
STATS_URL = os.environ.get("HY_STATS_URL", "http://127.0.0.1:9999/traffic")
STATS_SECRET = os.environ.get("HY_STATS_SECRET", "change_this_stats_secret")
PLAYIT_IP = os.environ.get("PLAYIT_IP", "<YOUR_PLAYIT_IPV4>")
PLAYIT_PORT = os.environ.get("PLAYIT_PORT", "17635")
HY_SNI = os.environ.get("HY_SNI", "bing.com")
ADMIN_USER = os.environ.get("HY_ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("HY_ADMIN_PASS", "ChangeMe123!")

DEFAULT_USERS = {
    "legacy": {"pass": "change_legacy_pass", "note": "Password-only compatible key"},
    "user1": {"pass": "change_user1_pass", "note": "Primary device"},
}


def load_users():
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    if not os.path.exists(USERS_FILE):
        save_users(DEFAULT_USERS)
        return dict(DEFAULT_USERS)
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_users(users):
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)


def get_stats():
    try:
        req = urllib.request.Request(STATS_URL, headers={"Authorization": STATS_SECRET})
        with urllib.request.urlopen(req, timeout=2) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {}


def fmt_bytes(b):
    if b < 1024:
        return f"{b} B"
    if b < 1024 ** 2:
        return f"{b / 1024:.1f} KB"
    if b < 1024 ** 3:
        return f"{b / (1024 ** 2):.2f} MB"
    return f"{b / (1024 ** 3):.2f} GB"


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ru" data-bs-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hysteria 2 Dashboard</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
<style>
  :root { --bg-main: #0b1120; --card-bg: #1e293b; --border-color: #334155; }
  body { background-color: var(--bg-main); color: #f1f5f9; font-family: system-ui, -apple-system, sans-serif; }
  .card { background-color: var(--card-bg) !important; border: 1px solid var(--border-color) !important; border-radius: 14px; }
  .badge-note { background: rgba(99, 102, 241, 0.15); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.3); font-size: 0.75rem; }
  .badge-tunnel { background: rgba(14, 165, 233, 0.15); color: #38bdf8; border: 1px solid rgba(14, 165, 233, 0.3); }
  .toast-container { position: fixed; bottom: 24px; right: 24px; z-index: 1060; }
  #qrcode-container img { margin: 0 auto; border-radius: 8px; padding: 8px; background: white; }
</style>
</head>
<body class="p-2 p-md-4">
<div class="container-fluid" style="max-width: 1180px;">
  <div class="d-flex flex-wrap justify-content-between align-items-center mb-4 pb-3 border-bottom border-secondary border-opacity-25">
    <div>
      <div class="d-flex align-items-center gap-2">
        <h3 class="fw-bold mb-0 text-white"><i class="bi bi-lightning-charge-fill text-warning me-1"></i>Hysteria 2 Panel</h3>
        <span class="badge bg-success-subtle text-success border border-success border-opacity-25 px-2 py-1">Online</span>
      </div>
      <div class="text-secondary small mt-1">
        Playit.gg UDP Endpoint: <span class="badge badge-tunnel font-monospace" id="endpoint-badge">--</span>
      </div>
    </div>
    <button class="btn btn-sm btn-outline-secondary mt-2 mt-md-0" onclick="loadData()"><i class="bi bi-arrow-clockwise me-1"></i>Обновить</button>
  </div>

  <div class="row g-3 mb-4">
    <div class="col-sm-4"><div class="card p-3"><div class="text-secondary small">Всего ключей</div><div class="h3 fw-bold mb-0 text-white mt-1" id="users-count">--</div></div></div>
    <div class="col-sm-4"><div class="card p-3"><div class="text-secondary small">Upload</div><div class="h3 fw-bold mb-0 text-info mt-1" id="total-tx">--</div></div></div>
    <div class="col-sm-4"><div class="card p-3"><div class="text-secondary small">Download</div><div class="h3 fw-bold mb-0 text-success mt-1" id="total-rx">--</div></div></div>
  </div>

  <div class="row g-4">
    <div class="col-lg-8">
      <div class="card p-3 p-md-4 h-100">
        <h5 class="fw-bold mb-3 text-white"><i class="bi bi-key-fill text-warning me-2"></i>Пользователи</h5>
        <div class="table-responsive">
          <table class="table table-hover align-middle mb-0">
            <thead>
              <tr class="text-secondary small"><th>Пользователь</th><th>Пароль</th><th>Трафик</th><th class="text-end">Действия</th></tr>
            </thead>
            <tbody id="users-tbody"><tr><td colspan="4" class="text-center text-secondary py-4">Загрузка...</td></tr></tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="col-lg-4">
      <div class="card p-3 p-md-4">
        <h5 class="fw-bold mb-3 text-white"><i class="bi bi-person-plus-fill text-success me-2"></i>Добавить ключ</h5>
        <form onsubmit="addUser(event)">
          <div class="mb-3">
            <label class="form-label small text-secondary">Логин</label>
            <input type="text" id="new-user" class="form-control bg-dark text-white border-secondary" required pattern="[a-zA-Z0-9_.\-]{2,24}">
          </div>
          <div class="mb-3">
            <div class="d-flex justify-content-between">
              <label class="form-label small text-secondary">Пароль</label>
              <a href="javascript:void(0)" class="small text-info text-decoration-none" onclick="genPass()">Сгенерировать</a>
            </div>
            <input type="text" id="new-pass" class="form-control bg-dark text-white border-secondary font-monospace" required>
          </div>
          <div class="mb-3">
            <label class="form-label small text-secondary">Заметка</label>
            <input type="text" id="new-note" class="form-control bg-dark text-white border-secondary">
          </div>
          <button type="submit" class="btn btn-primary w-100">Создать подключение</button>
        </form>
      </div>
    </div>
  </div>
</div>

<div class="modal fade" id="qrModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content card border-secondary">
      <div class="modal-header border-secondary border-opacity-25">
        <h5 class="modal-title fw-bold text-white">Подключение для <span id="modal-user"></span></h5>
        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body text-center p-4">
        <div id="qrcode-container" class="mb-3 d-flex justify-content-center"></div>
        <div class="input-group">
          <input type="text" id="modal-link-input" class="form-control bg-dark text-white border-secondary font-monospace small" readonly>
          <button class="btn btn-outline-info" onclick="copyFromModal()">Копировать</button>
        </div>
      </div>
    </div>
  </div>
</div>

<div class="toast-container">
  <div id="copy-toast" class="toast align-items-center text-bg-success border-0" role="alert">
    <div class="d-flex">
      <div class="toast-body">Ссылка скопирована!</div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
    </div>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
<script>
let linksMap = {};

function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function genPass() {
  const chars = 'abcdefghjkmnpqrstuvwxyz23456789ABCDEFGHJKLMNPQRSTUVWXYZ';
  let p = '';
  for (let i = 0; i < 14; i++) p += chars[Math.floor(Math.random() * chars.length)];
  document.getElementById('new-pass').value = p;
}

function showToast() {
  new bootstrap.Toast(document.getElementById('copy-toast'), { delay: 2500 }).show();
}

function copyLink(link) {
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(link).then(showToast).catch(() => fallbackCopy(link));
  } else {
    fallbackCopy(link);
  }
}

function fallbackCopy(text) {
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.left = '-999999px';
  document.body.appendChild(ta);
  ta.select();
  try {
    if (document.execCommand('copy')) showToast();
    else prompt('Скопируйте ссылку вручную:', text);
  } catch { prompt('Скопируйте ссылку вручную:', text); }
  document.body.removeChild(ta);
}

function showQRByUser(user) {
  const link = linksMap[user] || '';
  document.getElementById('modal-user').innerText = user;
  document.getElementById('modal-link-input').value = link;
  const container = document.getElementById('qrcode-container');
  container.innerHTML = '';
  new QRCode(container, { text: link, width: 220, height: 220, correctLevel: QRCode.CorrectLevel.M });
  new bootstrap.Modal(document.getElementById('qrModal')).show();
}

function copyFromModal() {
  copyLink(document.getElementById('modal-link-input').value);
}

function loadData() {
  fetch('/api/users').then(r => r.json()).then(data => {
    document.getElementById('endpoint-badge').innerText = `${data.endpoint.ip}:${data.endpoint.port}`;
    document.getElementById('users-count').innerText = Object.keys(data.users).length;
    document.getElementById('total-tx').innerText = data.total_tx_fmt;
    document.getElementById('total-rx').innerText = data.total_rx_fmt;
    const tbody = document.getElementById('users-tbody');
    linksMap = {};
    const entries = Object.entries(data.users);
    if (!entries.length) {
      tbody.innerHTML = '<tr><td colspan="4" class="text-center text-secondary py-4">Нет пользователей</td></tr>';
      return;
    }
    let html = '';
    for (const [user, info] of entries) {
      const link = (user === 'legacy')
        ? `hy2://${encodeURIComponent(info.pass)}@${data.endpoint.ip}:${data.endpoint.port}?insecure=1&sni=${encodeURIComponent(data.endpoint.sni)}#Playit-Hysteria2`
        : `hy2://${encodeURIComponent(user)}:${encodeURIComponent(info.pass)}@${data.endpoint.ip}:${data.endpoint.port}?insecure=1&sni=${encodeURIComponent(data.endpoint.sni)}#Hy2-${encodeURIComponent(user)}`;
      linksMap[user] = link;
      const st = data.stats[user] || { tx_fmt: '0 B', rx_fmt: '0 B' };
      const note = info.note ? `<div class="badge-note badge mt-1">${esc(info.note)}</div>` : '';
      html += `<tr>
        <td><div class="fw-bold text-white">${esc(user)}</div>${note}</td>
        <td><span class="font-monospace text-warning small">${esc(info.pass)}</span></td>
        <td class="small text-secondary"><span class="text-info">↑ ${esc(st.tx_fmt)}</span> · <span class="text-success">↓ ${esc(st.rx_fmt)}</span></td>
        <td class="text-end">
          <div class="d-inline-flex gap-1">
            <button class="btn btn-sm btn-outline-info" data-u="${esc(user)}" onclick="copyLink(linksMap[this.dataset.u])"><i class="bi bi-clipboard"></i></button>
            <button class="btn btn-sm btn-outline-light" data-u="${esc(user)}" onclick="showQRByUser(this.dataset.u)"><i class="bi bi-qr-code"></i></button>
            <button class="btn btn-sm btn-outline-danger" data-u="${esc(user)}" onclick="deleteUser(this.dataset.u)"><i class="bi bi-trash"></i></button>
          </div>
        </td>
      </tr>`;
    }
    tbody.innerHTML = html;
  });
}

function addUser(e) {
  e.preventDefault();
  const user = document.getElementById('new-user').value.trim();
  const pass = document.getElementById('new-pass').value.trim();
  const note = document.getElementById('new-note').value.trim();
  fetch('/api/users/add', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user, pass, note })
  }).then(() => {
    document.getElementById('new-user').value = '';
    document.getElementById('new-note').value = '';
    genPass();
    loadData();
  });
}

function deleteUser(user) {
  if (!confirm(`Удалить ключ "${user}"?`)) return;
  fetch('/api/users/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user })
  }).then(() => loadData());
}

genPass();
loadData();
setInterval(loadData, 5000);
</script>
</body>
</html>
"""


class SimpleAuthHandler(BaseHTTPRequestHandler):
    def check_auth(self):
        auth_header = self.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Basic "):
            return False
        try:
            decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
            u, p = decoded.split(":", 1)
            return secrets.compare_digest(u, ADMIN_USER) and secrets.compare_digest(p, ADMIN_PASS)
        except Exception:
            return False

    def require_auth(self):
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Hysteria Panel"')
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Unauthorized")

    def _send_json(self, code, payload):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json(200, {"status": "running"})
            return

        client_ip = self.client_address[0]
        if not self.check_auth() and client_ip not in ("127.0.0.1", "::1"):
            self.require_auth()
            return

        if parsed.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
        elif parsed.path == "/api/users":
            users = load_users()
            stats = get_stats()
            formatted_stats = {}
            tot_tx = 0
            tot_rx = 0
            for u in users:
                s = stats.get(u, {})
                tx = int(s.get("tx", 0))
                rx = int(s.get("rx", 0))
                tot_tx += tx
                tot_rx += rx
                formatted_stats[u] = {
                    "tx": tx,
                    "rx": rx,
                    "tx_fmt": fmt_bytes(tx),
                    "rx_fmt": fmt_bytes(rx),
                }
            self._send_json(200, {
                "endpoint": {"ip": PLAYIT_IP, "port": PLAYIT_PORT, "sni": HY_SNI},
                "users": users,
                "stats": formatted_stats,
                "total_tx_fmt": fmt_bytes(tot_tx),
                "total_rx_fmt": fmt_bytes(tot_rx),
            })
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            data = json.loads(body.decode("utf-8"))
        except Exception:
            data = {}

        if parsed.path in ("/api/auth", "/auth"):
            auth_str = str(data.get("auth", "")).strip()
            users = load_users()
            matched = None
            if ":" in auth_str:
                u, p = auth_str.split(":", 1)
                if u in users and secrets.compare_digest(users[u].get("pass", ""), p):
                    matched = u
            else:
                for u, uinfo in users.items():
                    if secrets.compare_digest(uinfo.get("pass", ""), auth_str):
                        matched = u
                        break
            if matched:
                self._send_json(200, {"ok": True, "id": matched})
            else:
                self._send_json(200, {"ok": False})
            return

        client_ip = self.client_address[0]
        if not self.check_auth() and client_ip not in ("127.0.0.1", "::1"):
            self.require_auth()
            return

        if parsed.path == "/api/users/add":
            u = str(data.get("user", "")).strip()
            p = str(data.get("pass", "")).strip()
            n = str(data.get("note", "")).strip()
            if u and p:
                users = load_users()
                users[u] = {"pass": p, "note": n}
                save_users(users)
                self._send_json(200, {"status": "ok"})
            else:
                self.send_response(400)
                self.end_headers()
        elif parsed.path == "/api/users/delete":
            u = str(data.get("user", "")).strip()
            users = load_users()
            if u in users:
                del users[u]
                save_users(users)
            self._send_json(200, {"status": "ok"})
        else:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    print(f"Hysteria 2 Panel listening on 0.0.0.0:{PORT}")
    HTTPServer(("0.0.0.0", PORT), SimpleAuthHandler).serve_forever()
