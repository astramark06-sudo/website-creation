"""Original local-only data workspace. Not a public multi-user server."""
import argparse
import json
import secrets
import re
import sqlite3
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parent
LIMIT = 1000


def validate_fields(fields):
    if not isinstance(fields, list) or len(fields) > 6:
        raise ValueError("Invalid field definitions")
    seen = set()
    for field in fields:
        if not isinstance(field, dict):
            raise ValueError("Invalid field")
        kind = field.get("type")
        keys = {"id", "label", "type"} | ({"choices"} if kind == "choice" else set())
        if set(field) != keys or kind not in ("integer", "text", "choice"):
            raise ValueError("Invalid field type")
        name, label = field["id"], field["label"]
        if (not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", name)
                or name in seen or not isinstance(label, str) or not label.strip() or len(label) > 80):
            raise ValueError("Invalid or duplicate field")
        seen.add(name)
        if kind == "choice":
            options = field["choices"]
            if (not isinstance(options, list) or not 1 <= len(options) <= 12
                    or any(not isinstance(v, str) or not v.strip() or len(v) > 80 for v in options)
                    or len(set(options)) != len(options)):
                raise ValueError("Invalid choices")
    return fields


def validate_details(fields, details):
    if not isinstance(details, dict) or set(details) != {f["id"] for f in fields}:
        raise ValueError("Missing or unknown model fields")
    for field in fields:
        value = details[field["id"]]
        kind = field["type"]
        if kind == "integer" and (type(value) is not int or not 0 <= value <= 1000000):
            raise ValueError("Use an integer from 0 to 1000000")
        if kind == "text" and (not isinstance(value, str) or len(value) > 160):
            raise ValueError("Text field exceeds limit")
        if kind == "choice" and value not in field["choices"]:
            raise ValueError("Unknown choice")
    return details


def database(path, fields=None):
    fields = validate_fields([] if fields is None else fields)
    schema = json.dumps(fields, sort_keys=True, separators=(",", ":"))
    db = sqlite3.connect(path, timeout=5)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA foreign_keys=ON")
        with db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, title TEXT NOT NULL, notes TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0)")
            db.execute("CREATE TABLE IF NOT EXISTS model_schema (id INTEGER PRIMARY KEY CHECK(id=1), definition TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS item_details (item_id INTEGER PRIMARY KEY REFERENCES items(id) ON DELETE CASCADE, data TEXT NOT NULL)")
            current = db.execute("SELECT definition FROM model_schema WHERE id=1").fetchone()
            if current is None:
                if fields and db.execute("SELECT count(*) FROM items").fetchone()[0]:
                    raise ValueError("Use a new database for a different model")
                db.execute("INSERT INTO model_schema VALUES (1,?)", (schema,))
            elif current[0] != schema:
                raise ValueError("Database model mismatch; use the original configuration")
        return db
    except BaseException:
        db.close()
        raise


def list_items(path, query="", state="all", fields=None):
    fields = validate_fields([] if fields is None else fields)
    if not isinstance(query, str) or state not in ("all", "open", "done") or len(query) > 200:
        raise ValueError("Invalid filter")
    with closing(database(path, fields)) as db:
        rows = db.execute(
            "SELECT items.id,title,notes,done,item_details.data FROM items "
            "LEFT JOIN item_details ON item_details.item_id=items.id "
            "WHERE (?='all' OR done=?) ORDER BY items.id DESC LIMIT ?",
            (state, int(state == "done"), LIMIT),
        ).fetchall()
        result = []
        for row in rows:
            item = {k: row[k] for k in ("id", "title", "notes", "done")}
            values = []
            if fields:
                item["details"] = validate_details(fields, json.loads(row["data"] or "{}"))
                values = [str(value) for value in item["details"].values()]
            if not query or any(query.casefold() in value.casefold()
                                for value in [item["title"], item["notes"], *values]):
                result.append(item)
        return result


def change_item(path, payload, fields=None):
    fields = validate_fields([] if fields is None else fields)
    if not isinstance(payload, dict):
        raise ValueError("Expected object")
    action = payload.get("action")
    keys = {"add": {"action", "title", "notes"}, "edit": {"action", "id", "title", "notes"},
            "toggle": {"action", "id"}, "delete": {"action", "id"}}
    if fields:
        keys["add"].add("details")
        keys["edit"].add("details")
    if not isinstance(action, str) or action not in keys or set(payload) != keys[action]:
        raise ValueError("Invalid action")
    if action in ("add", "edit"):
        title, notes = payload["title"], payload["notes"]
        if not isinstance(title, str) or not title.strip() or len(title) > 160 or not isinstance(notes, str) or len(notes) > 2000:
            raise ValueError("Invalid title or notes")
        details = validate_details(fields, payload.get("details", {}))
    if action != "add" and (type(payload["id"]) is not int or not 1 <= payload["id"] <= 2**63-1):
        raise ValueError("Invalid item id")
    with closing(database(path, fields)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        if action == "add":
            if db.execute("SELECT count(*) FROM items").fetchone()[0] >= LIMIT:
                raise ValueError("Item limit reached")
            result = db.execute("INSERT INTO items(title,notes) VALUES (?,?)", (title.strip(), notes))
            item_id = result.lastrowid
        elif action == "edit":
            result = db.execute("UPDATE items SET title=?,notes=? WHERE id=?", (title.strip(), notes, payload["id"]))
            item_id = payload["id"]
        elif action == "toggle":
            result = db.execute("UPDATE items SET done=1-done WHERE id=?", (payload["id"],))
        else:
            result = db.execute("DELETE FROM items WHERE id=?", (payload["id"],))
        if action != "add" and result.rowcount != 1:
            raise ValueError("Item not found")
        if fields and action in ("add", "edit"):
            db.execute("INSERT INTO item_details(item_id,data) VALUES (?,?) "
                       "ON CONFLICT(item_id) DO UPDATE SET data=excluded.data",
                       (item_id, json.dumps(details, ensure_ascii=False, sort_keys=True)))


def handler(port, token, db_path):
    host = f"127.0.0.1:{port}"
    origin = "http://" + host
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    fields = validate_fields(config.get("fields", []))

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
                    self.reply(200, {"token": token, "config": config})
                elif parsed.path == "/api/items":
                    if not secrets.compare_digest(self.headers.get("X-Workspace-Token", ""), token):
                        self.reply(403, {"error": "Invalid session"})
                        return
                    params = parse_qs(parsed.query, max_num_fields=4)
                    self.reply(200, {"items": list_items(db_path, params.get("q", [""])[0], params.get("state", ["all"])[0], fields)})
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
                change_item(db_path, json.loads(self.rfile.read(length)), fields)
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
