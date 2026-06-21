from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import hashlib
import html
import json
import os
import secrets
import socket
import sqlite3
import subprocess
import sys
import threading
import time


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = ROOT / "operator_dashboard"
DATA_DIR = DASHBOARD_DIR / "data"
USERS_DB = DATA_DIR / "operators.db"
SEP_DB = ROOT / "server" / "database" / "ieee2030.db"
RUNTIME_LOG = ROOT / "server_runtime.log"
HOST = "0.0.0.0"
PORT = int(os.environ.get("OPERATOR_DASHBOARD_PORT", "8080"))

SESSIONS = {}
SEP_PROCESS = None


def init_auth_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(USERS_DB) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS operators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'approved',
                reviewed_at INTEGER
            )
            """
        )
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(operators)").fetchall()
        }
        if "status" not in columns:
            conn.execute("ALTER TABLE operators ADD COLUMN status TEXT NOT NULL DEFAULT 'approved'")
        if "reviewed_at" not in columns:
            conn.execute("ALTER TABLE operators ADD COLUMN reviewed_at INTEGER")


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        120000,
    ).hex()
    return digest, salt


def create_operator(username, password):
    username = username.strip()
    if not username or not password:
        raise ValueError("Username and password are required")

    password_hash, salt = hash_password(password)
    with sqlite3.connect(USERS_DB) as conn:
        conn.execute(
            """
            INSERT INTO operators (username, password_hash, salt, created_at, status)
            VALUES (?, ?, ?, ?, 'pending')
            """,
            (username, password_hash, salt, int(time.time())),
        )
    print()
    print(f"[operator approval] Registration request received for: {username}")
    print(f"[operator approval] Type: approve {username}")
    print(f"[operator approval] Or type: reject {username}")
    print()


def authenticate(username, password):
    with sqlite3.connect(USERS_DB) as conn:
        row = conn.execute(
            "SELECT username, password_hash, salt, status FROM operators WHERE username=?",
            (username.strip(),),
        ).fetchone()

    if not row:
        return None

    expected, _ = hash_password(password, row[2])
    if not secrets.compare_digest(expected, row[1]):
        return None
    return row[0] if row[3] == "approved" else None


def list_pending_operators():
    with sqlite3.connect(USERS_DB) as conn:
        return conn.execute(
            "SELECT username, created_at FROM operators WHERE status='pending' ORDER BY created_at"
        ).fetchall()


def set_operator_status(username, status):
    with sqlite3.connect(USERS_DB) as conn:
        cur = conn.execute(
            "UPDATE operators SET status=?, reviewed_at=? WHERE username=?",
            (status, int(time.time()), username.strip()),
        )
        return cur.rowcount > 0


def approval_console():
    if not sys.stdin or not sys.stdin.isatty():
        return

    print("[operator approval] Commands: pending | approve <username> | reject <username>")
    while True:
        try:
            command = input("[operator approval] > ").strip()
        except EOFError:
            return

        if not command:
            continue
        if command == "pending":
            pending = list_pending_operators()
            if not pending:
                print("[operator approval] No pending operators.")
            for username, created_at in pending:
                print(f"[operator approval] pending: {username} at {created_at}")
            continue

        parts = command.split(maxsplit=1)
        if len(parts) != 2 or parts[0] not in {"approve", "reject"}:
            print("[operator approval] Use: pending | approve <username> | reject <username>")
            continue

        status = "approved" if parts[0] == "approve" else "rejected"
        if set_operator_status(parts[1], status):
            print(f"[operator approval] {parts[1]} marked as {status}.")
        else:
            print(f"[operator approval] Operator not found: {parts[1]}")


def is_sep_process_running():
    global SEP_PROCESS
    if SEP_PROCESS is not None and SEP_PROCESS.poll() is None:
        return True
    return is_sep_port_open()


def is_sep_port_open():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.35)
        return sock.connect_ex(("127.0.0.1", 8443)) == 0


def start_sep_server():
    global SEP_PROCESS
    if is_sep_process_running():
        return True, "SEP server is already running."

    cmd = [sys.executable, "-m", "server.main"]
    log_path = ROOT / "dashboard_started_sep.log"
    log_file = open(log_path, "ab")
    SEP_PROCESS = subprocess.Popen(
        cmd,
        cwd=ROOT,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    time.sleep(0.7)

    if SEP_PROCESS.poll() is None:
        return True, "SEP server start command launched."
    return False, "SEP server exited immediately. Check dashboard_started_sep.log."


def stop_sep_server():
    global SEP_PROCESS
    stopped = False

    if SEP_PROCESS is not None and SEP_PROCESS.poll() is None:
        SEP_PROCESS.terminate()
        try:
            SEP_PROCESS.wait(timeout=5)
        except subprocess.TimeoutExpired:
            SEP_PROCESS.kill()
        stopped = True

    if not stopped and is_sep_port_open() and os.name == "posix":
        result = subprocess.run(
            ["pkill", "-f", "python.*-m server.main"],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        stopped = result.returncode == 0

    time.sleep(0.5)
    if not is_sep_port_open():
        return True, "SEP server stopped."
    if stopped:
        return False, "Stop command sent, but port 8443 still appears active."
    return False, "SEP server was not started by this dashboard, or stop permission is unavailable."


def read_runtime_log(limit=80):
    if not RUNTIME_LOG.exists():
        return ["server_runtime.log has not been created yet."]
    lines = RUNTIME_LOG.read_text(errors="replace").splitlines()
    return lines[-limit:]


def fetch_tables():
    if not SEP_DB.exists():
        return []

    with sqlite3.connect(f"file:{SEP_DB}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()

        result = []
        for table in tables:
            name = table["name"]
            if name.startswith("sqlite_"):
                continue
            rows = conn.execute(f'SELECT * FROM "{name}" LIMIT 25').fetchall()
            columns = rows[0].keys() if rows else []
            count = conn.execute(f'SELECT COUNT(*) AS c FROM "{name}"').fetchone()["c"]
            result.append(
                {
                    "name": name,
                    "count": count,
                    "columns": list(columns),
                    "rows": [dict(row) for row in rows],
                }
            )
        return result


def latest_measurement():
    if not SEP_DB.exists():
        return None
    try:
        with sqlite3.connect(f"file:{SEP_DB}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                "SELECT * FROM mup_log ORDER BY id DESC LIMIT 1"
            ).fetchone()
    except sqlite3.Error:
        return None


def measurement_history(limit=80):
    if not SEP_DB.exists():
        return []
    try:
        with sqlite3.connect(f"file:{SEP_DB}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            return [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT *
                    FROM (
                        SELECT * FROM mup_log ORDER BY id DESC LIMIT ?
                    )
                    ORDER BY id ASC
                    """,
                    (limit,),
                ).fetchall()
            ]
    except sqlite3.Error:
        return []


def count_table(name):
    if not SEP_DB.exists():
        return 0
    try:
        with sqlite3.connect(f"file:{SEP_DB}?mode=ro", uri=True) as conn:
            return conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
    except sqlite3.Error:
        return 0


def client_summary():
    lines = read_runtime_log(500)
    clients = {}
    for line in lines:
        marker = " request from "
        if marker not in line:
            continue
        try:
            ip_and_path = line.split(marker, 1)[1]
            ip, path = ip_and_path.split(" -> ", 1)
            method = line.rsplit("[INFO] ", 1)[-1].split(" request", 1)[0]
            clients.setdefault(ip, {"count": 0, "last": "", "method": ""})
            clients[ip]["count"] += 1
            clients[ip]["last"] = path
            clients[ip]["method"] = method
        except ValueError:
            continue
    return clients


def live_payload():
    measurement = latest_measurement()
    measurement_dict = dict(measurement) if measurement else None
    return {
        "serverRunning": is_sep_process_running(),
        "databaseOnline": SEP_DB.exists(),
        "runtimeLogOnline": RUNTIME_LOG.exists(),
        "latestMeasurement": measurement_dict,
        "history": measurement_history(),
        "logs": read_runtime_log(40),
        "clients": client_summary(),
        "tableCounts": {
            "mup_log": count_table("mup_log"),
            "der_controls": count_table("der_controls"),
            "end_devices": count_table("end_devices"),
        },
    }


def html_page(title, body, active="dashboard"):
    nav = [
        ("dashboard", "/dashboard", "Dashboard"),
        ("tables", "/tables", "Tables"),
        ("logs", "/logs", "Logs"),
        ("clients", "/clients", "Clients"),
    ]
    nav_html = "".join(
        f'<a class="nav-link {"active" if key == active else ""}" href="{href}">{label}</a>'
        for key, href, label in nav
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="/static/style.css">
  <script defer src="/static/theme.js"></script>
  <script defer src="/static/dashboard.js"></script>
</head>
<body>
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-mark"><span></span></div>
      <div>
        <strong>GRID SENTINEL SEP</strong>
        <span>IEEE 2030.5 Control</span>
      </div>
    </div>
    <button class="theme-toggle sidebar-theme-toggle" type="button" data-theme-toggle aria-label="Switch to light mode" title="Switch theme">
      <span class="theme-icon" aria-hidden="true">D</span>
      <span data-theme-label>Dark</span>
    </button>
    <nav>{nav_html}</nav>
    <a class="logout" href="/logout">Logout</a>
  </aside>
  <main class="content">{body}</main>
</body>
</html>"""


def auth_page(mode, message=""):
    is_register = mode == "register"
    title = "Register Operator" if is_register else "Operator Login"
    action = "/register" if is_register else "/login"
    switch_href = "/login" if is_register else "/register"
    switch_text = "Already registered? Login" if is_register else "Create operator account"
    message_html = f'<p class="notice">{html.escape(message)}</p>' if message else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GRID SENTINEL SEP - {title}</title>
  <link rel="stylesheet" href="/static/style.css">
  <script defer src="/static/theme.js"></script>
</head>
<body class="auth-body">
  <button class="theme-toggle" type="button" data-theme-toggle aria-label="Switch to light mode" title="Switch theme">
    <span class="theme-icon" aria-hidden="true">D</span>
    <span data-theme-label>Dark</span>
  </button>
  <section class="auth-shell">
    <div class="auth-visual">
      <div class="grid-glow"></div>
      <div class="hero-logo"><div class="brand-mark large"><span></span></div><strong>GRID SENTINEL SEP</strong></div>
      <h1>Electrical command center for IEEE 2030.5 operations</h1>
      <p>Monitor DER communication, metering updates, controls, client activity, and server health from one secured dashboard.</p>
      <div class="metric-strip">
        <span>mTLS</span><span>DER</span><span>MUP</span><span>Controls</span>
      </div>
    </div>
    <form class="auth-card" method="post" action="{action}">
      <div class="form-brand">GRID SENTINEL SEP</div>
      <h2>{title}</h2>
      {message_html}
      <label>Username<input name="username" autocomplete="username" required></label>
      <label>Password<input name="password" type="password" autocomplete="current-password" required></label>
      <button type="submit">{title}</button>
      <p class="auth-note">New registrations stay pending until the developer approves them in the dashboard terminal.</p>
      <a href="{switch_href}">{switch_text}</a>
    </form>
  </section>
</body>
</html>"""


def render_dashboard(message=""):
    measurement = latest_measurement()
    server_state = "Running" if is_sep_process_running() else "Stopped"
    metric_cards = [
        ("Server", server_state, "server-state"),
        ("Database", "Online" if SEP_DB.exists() else "Missing", "database-state"),
        ("Runtime Log", "Enabled" if RUNTIME_LOG.exists() else "Waiting", "log-state"),
        ("End Devices", str(count_table("end_devices")), "end-device-count"),
    ]

    if measurement:
        metric_cards.extend(
            [
                ("Voltage A", f"{measurement['voltage_a']} V", "voltage-a"),
                ("Voltage B", f"{measurement['voltage_b']} V", "voltage-b"),
                ("Voltage C", f"{measurement['voltage_c']} V", "voltage-c"),
                ("Frequency", f"{measurement['frequency']} Hz", "frequency"),
            ]
        )

    cards = "".join(
        f'<article class="metric"><span>{html.escape(label)}</span><strong id="{dom_id}">{html.escape(str(value))}</strong></article>'
        for label, value, dom_id in metric_cards
    )
    notice = f'<p class="notice">{html.escape(message)}</p>' if message else ""
    body = f"""
      <header class="page-head">
        <div><h1>GRID SENTINEL SEP</h1><p>Live electrical operations, DER client telemetry, and IEEE 2030.5 server control.</p></div>
        <div class="server-actions">
          <form method="post" action="/server/start"><button class="primary" type="submit">Start Server</button></form>
          <form method="post" action="/server/stop"><button class="danger" type="submit">Stop Server</button></form>
        </div>
      </header>
      {notice}
      <section class="metrics">{cards}</section>
      <section class="dashboard-grid">
        <article class="panel">
          <div class="panel-title"><h2>3-Phase Voltages</h2><span>live</span></div>
          <canvas id="voltage-chart" height="220"></canvas>
        </article>
        <article class="panel">
          <div class="panel-title"><h2>3-Phase Power</h2><span>live</span></div>
          <canvas id="power-chart" height="220"></canvas>
        </article>
        <article class="panel">
          <div class="panel-title"><h2>Frequency</h2><span>live</span></div>
          <canvas id="frequency-chart" height="220"></canvas>
        </article>
        <article class="panel">
          <div class="panel-title"><h2>End Device Status</h2><span>IEEE 2030.5</span></div>
          <p class="muted" id="end-device-note">The active server currently serves /edev/1 from XML but has not inserted rows into end_devices.</p>
        </article>
      </section>
      <section class="panel">
        <h2>Recent Runtime Events</h2>
        <pre class="logbox" id="runtime-log">{html.escape(chr(10).join(read_runtime_log(18)))}</pre>
      </section>
    """
    return html_page("Dashboard", body, "dashboard")


def render_tables():
    sections = []
    for table in fetch_tables():
        headers = "".join(f"<th>{html.escape(col)}</th>" for col in table["columns"])
        rows = ""
        for row in table["rows"]:
            rows += "<tr>" + "".join(
                f"<td>{html.escape(str(row.get(col, '')))}</td>" for col in table["columns"]
            ) + "</tr>"
        if not rows:
            rows = '<tr><td class="muted">No rows</td></tr>'
        sections.append(
            f"""
            <section class="panel">
              <div class="panel-title"><h2>{html.escape(table['name'])}</h2><span>{table['count']} rows</span></div>
              <div class="table-wrap"><table><thead><tr>{headers}</tr></thead><tbody>{rows}</tbody></table></div>
            </section>
            """
        )
    body = "<header class='page-head'><div><h1>Database Tables</h1><p>Read-only view of active SEP database tables.</p></div></header>"
    body += "".join(sections) or "<section class='panel'>No database tables found.</section>"
    return html_page("Tables", body, "tables")


def render_logs():
    body = f"""
      <header class="page-head"><div><h1>Runtime Logs</h1><p>Latest entries from server_runtime.log.</p></div></header>
      <section class="panel"><pre class="logbox tall">{html.escape(chr(10).join(read_runtime_log(160)))}</pre></section>
    """
    return html_page("Logs", body, "logs")


def render_clients():
    lines = read_runtime_log(300)
    clients = {}
    for line in lines:
        marker = " request from "
        if marker not in line:
            continue
        try:
            ip_and_path = line.split(marker, 1)[1]
            ip, path = ip_and_path.split(" -> ", 1)
            clients.setdefault(ip, {"count": 0, "last": ""})
            clients[ip]["count"] += 1
            clients[ip]["last"] = path
        except ValueError:
            continue

    rows = "".join(
        f"<tr><td>{html.escape(ip)}</td><td>{data['count']}</td><td>{html.escape(data['last'])}</td></tr>"
        for ip, data in clients.items()
    )
    rows = rows or '<tr><td class="muted" colspan="3">No client requests logged yet.</td></tr>'
    body = f"""
      <header class="page-head"><div><h1>Client Visualization</h1><p>DER/client request activity inferred from runtime logs.</p></div></header>
      <section class="panel"><div class="table-wrap"><table><thead><tr><th>Client IP</th><th>Requests</th><th>Last Path</th></tr></thead><tbody>{rows}</tbody></table></div></section>
    """
    return html_page("Clients", body, "clients")


def parse_form(handler):
    length = int(handler.headers.get("Content-Length", 0))
    body = handler.rfile.read(length).decode("utf-8")
    data = parse_qs(body)
    return {key: values[0] for key, values in data.items()}


class DashboardHandler(BaseHTTPRequestHandler):
    def current_user(self):
        raw = self.headers.get("Cookie", "")
        jar = cookies.SimpleCookie(raw)
        sid = jar.get("sid")
        if not sid:
            return None
        return SESSIONS.get(sid.value)

    def send_html(self, content, status=200):
        encoded = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def require_auth(self):
        if self.current_user():
            return True
        self.redirect("/login")
        return False

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/static/style.css":
            css = (DASHBOARD_DIR / "static" / "style.css").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/css")
            self.send_header("Content-Length", str(len(css)))
            self.end_headers()
            self.wfile.write(css)
            return
        if path == "/static/dashboard.js":
            js = (DASHBOARD_DIR / "static" / "dashboard.js").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript")
            self.send_header("Content-Length", str(len(js)))
            self.end_headers()
            self.wfile.write(js)
            return
        if path == "/static/theme.js":
            js = (DASHBOARD_DIR / "static" / "theme.js").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript")
            self.send_header("Content-Length", str(len(js)))
            self.end_headers()
            self.wfile.write(js)
            return

        if path in ("/", "/login"):
            self.send_html(auth_page("login"))
            return
        if path == "/register":
            self.send_html(auth_page("register"))
            return
        if path == "/logout":
            raw = self.headers.get("Cookie", "")
            jar = cookies.SimpleCookie(raw)
            if "sid" in jar:
                SESSIONS.pop(jar["sid"].value, None)
            self.redirect("/login")
            return

        if not self.require_auth():
            return

        if path == "/dashboard":
            self.send_html(render_dashboard())
        elif path == "/tables":
            self.send_html(render_tables())
        elif path == "/logs":
            self.send_html(render_logs())
        elif path == "/clients":
            self.send_html(render_clients())
        elif path == "/api/status":
            payload = json.dumps({"sep_running": is_sep_process_running()}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        elif path == "/api/live":
            payload = json.dumps(live_payload()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        else:
            self.send_html(render_dashboard("Page not found."), 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/register":
            form = parse_form(self)
            try:
                create_operator(form.get("username", ""), form.get("password", ""))
                self.send_html(auth_page("login", "Registration request sent. Login is enabled after developer approval in the terminal."))
            except sqlite3.IntegrityError:
                self.send_html(auth_page("register", "That username already exists."), 400)
            except ValueError as exc:
                self.send_html(auth_page("register", str(exc)), 400)
            return

        if path == "/login":
            form = parse_form(self)
            username = authenticate(form.get("username", ""), form.get("password", ""))
            if not username:
                self.send_html(auth_page("login", "Invalid username or password."), 401)
                return
            sid = secrets.token_urlsafe(32)
            SESSIONS[sid] = username
            self.send_response(303)
            self.send_header("Location", "/dashboard")
            self.send_header("Set-Cookie", f"sid={sid}; HttpOnly; SameSite=Lax; Path=/")
            self.end_headers()
            return

        if not self.require_auth():
            return

        if path == "/server/start":
            ok, message = start_sep_server()
            status = 200 if ok else 500
            self.send_html(render_dashboard(message), status)
        elif path == "/server/stop":
            ok, message = stop_sep_server()
            status = 200 if ok else 500
            self.send_html(render_dashboard(message), status)
        else:
            self.send_html(render_dashboard("Unsupported action."), 404)


def main():
    init_auth_db()
    threading.Thread(target=approval_console, daemon=True).start()
    httpd = ThreadingHTTPServer((HOST, PORT), DashboardHandler)
    print(f"Operator dashboard running on http://{HOST}:{PORT}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
