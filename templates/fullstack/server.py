"""Original local-only data workspace. Not a public multi-user server."""
import argparse
import json
import secrets
import sqlite3
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parent
LIMIT = 1000


def database(path):
    db = sqlite3.connect(path, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, title TEXT NOT NULL, notes TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0)")
    return db


def list_items(path, query="", state="all"):
    if state not in ("all", "open", "done") or len(query) > 200:
        raise ValueError("Invalid filter")
    with closing(database(path)) as db:
        rows = db.execute(
            "SELECT id,title,notes,done FROM items WHERE "
            "(instr(lower(title),lower(?))>0 OR instr(lower(notes),lower(?))>0) "
            "AND (?='all' OR done=?) ORDER BY id DESC LIMIT ?",
            (query, query, state, int(state == "done"), LIMIT),
        ).fetchall()
        return [dict(row) for row in rows]


def change_item(path, payload):
    if not isinstance(payload, dict):
        raise ValueError("Expected object")
    action = payload.get("action")
    keys = {"add": {"action", "title", "notes"}, "edit": {"action", "id", "title", "notes"},
            "toggle": {"action", "id"}, "delete": {"action", "id"}}
    if not isinstance(action, str) or action not in keys or set(payload) != keys[action]:
        raise ValueError("Invalid action")
    if action in ("add", "edit"):
        title, notes = payload["title"], payload["notes"]
        if not isinstance(title, str) or not title.strip() or len(title) > 160 or not isinstance(notes, str) or len(notes) > 2000:
            raise ValueError("Invalid title or notes")
    if action != "add" and (type(payload["id"]) is not int or not 1 <= payload["id"] <= 2**63-1):
        raise ValueError("Invalid item id")
    with closing(database(path)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        if action == "add":
            if db.execute("SELECT count(*) FROM items").fetchone()[0] >= LIMIT:
                raise ValueError("Item limit reached")
            db.execute("INSERT INTO items(title,notes) VALUES (?,?)", (title.strip(), notes))
        elif action == "edit":
            result = db.execute("UPDATE items SET title=?,notes=? WHERE id=?", (title.strip(), notes, payload["id"]))
        elif action == "toggle":
            result = db.execute("UPDATE items SET done=1-done WHERE id=?", (payload["id"],))
        else:
            result = db.execute("DELETE FROM items WHERE id=?", (payload["id"],))
        if action != "add" and result.rowcount != 1:
            raise ValueError("Item not found")


def handler(port, token, db_path):
    host = f"127.0.0.1:{port}"
    origin = "http://" + host

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, *args):
            pass

        def send_data(self, status, data, mime):
            self.send_response(status)
            for key, value in {
                "Content-Type": mime, "Content-Length": str(len(data)),
                "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; form-action 'none'; frame-ancestors 'none'; base-uri 'none'",
            }.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(data)

        def reply(self, status, value):
            self.send_data(status, json.dumps(value).encode(), "application/json; charset=utf-8")

        def allowed(self, mutation=False):
            if self.headers.get("Host") != host:
                self.reply(403, {"error": "Invalid host"})
                return False
            if mutation and (self.headers.get("Origin") != origin or not secrets.compare_digest(self.headers.get("X-Workspace-Token", ""), token)):
                self.reply(403, {"error": "Invalid session"})
                return False
            return True

        def do_GET(self):
            if not self.allowed():
                return
            parsed = urlsplit(self.path)
            routes = {"/": ("index.html", "text/html; charset=utf-8"),
                      "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                      "/style.css": ("style.css", "text/css; charset=utf-8")}
            try:
                if parsed.path in routes:
                    name, mime = routes[parsed.path]
                    self.send_data(200, (ROOT / name).read_bytes(), mime)
                elif parsed.path == "/api/session":
                    self.reply(200, {"token": token, "config": json.loads((ROOT / "config.json").read_text(encoding="utf-8"))})
                elif parsed.path == "/api/items":
                    if not secrets.compare_digest(self.headers.get("X-Workspace-Token", ""), token):
                        self.reply(403, {"error": "Invalid session"})
                        return
                    params = parse_qs(parsed.query, max_num_fields=4)
                    self.reply(200, {"items": list_items(db_path, params.get("q", [""])[0], params.get("state", ["all"])[0])})
                else:
                    self.reply(404, {"error": "Not found"})
            except (ValueError, OSError, sqlite3.Error):
                self.reply(400, {"error": "Unable to read workspace"})

        def do_POST(self):
            if not self.allowed(mutation=True):
                return
            if self.path != "/api/items":
                self.reply(404, {"error": "Not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "-1"))
                if self.headers.get_content_type() != "application/json" or not 0 < length <= 16384:
                    raise ValueError("Invalid request")
                change_item(db_path, json.loads(self.rfile.read(length)))
                self.reply(200, {"ok": True})
            except (ValueError, OSError, sqlite3.Error):
                self.reply(400, {"error": "Unable to update item; check fields and limits"})

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Choose a port from 1024 to 65535")
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler(args.port, secrets.token_urlsafe(32), ROOT / "workspace.sqlite3")) as server:
        print(f"Local workspace: http://127.0.0.1:{args.port}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
