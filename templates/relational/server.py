"""Local-only relational workspace; not a production or multi-user server."""
import argparse
import json
from pathlib import Path
import secrets
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs

import creator_relational as rel

ROOT = Path(__file__).resolve().parent
ROUTES = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/style.css": ("style.css", "text/css; charset=utf-8")}
CSP = "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; form-action 'none'; frame-ancestors 'none'; base-uri 'none'"


def config_for(root):
    with (root / "config.json").open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError("Configuration exceeds limit")
    config = json.loads(raw.decode("utf-8"), object_pairs_hook=rel.unique_object, parse_constant=rel.reject_constant)
    if not isinstance(config, dict) or set(config) != {"title", "description", "schema"}:
        raise ValueError("Invalid configuration")
    rel.require_text(config["title"], "title", 120)
    rel.require_text(config["description"], "description", 1000)
    config["schema"] = rel.validate_schema(config["schema"])
    return config


def records_response(path, schema, table):
    definition = rel.table_definition(schema, table)
    records = rel.list_records(path, schema, table)
    options = {}
    for field in definition["fields"]:
        if field["type"] != "relation" or field["target"] in options:
            continue
        target = field["target"]
        target_def = rel.table_definition(schema, target)
        label_field = next((f["id"] for f in target_def["fields"] if f["type"] == "text"), None)
        options[target] = [{"id": item["id"], "label": (item["values"].get(label_field) or "Record") + " (#" + str(item["id"]) + ")"}
                           for item in rel.list_records(path, schema, target)]
    return {"records": records, "options": options}


def mutation(path, schema, data):
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object")
    action = data.get("action")
    keys = {"add": {"action", "table", "values"}, "edit": {"action", "table", "id", "values"},
            "delete": {"action", "table", "id"}}
    if not isinstance(action, str) or action not in keys or set(data) != keys[action]:
        raise ValueError("Invalid action")
    if action == "add":
        return {"id": rel.add_record(path, schema, data["table"], data["values"])}
    if action == "edit":
        rel.edit_record(path, schema, data["table"], data["id"], data["values"])
    else:
        rel.delete_record(path, schema, data["table"], data["id"])
    return {"ok": True}


def make_handler(port, token, root=ROOT):
    root = Path(root)
    config = config_for(root)
    schema = config["schema"]
    db_path = root / "workspace.sqlite3"
    if not db_path.exists():
        rel.create_database(db_path, schema)
    with rel.connect(db_path, schema):
        pass
    host = f"127.0.0.1:{port}"
    origin = "http://" + host

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, *args):
            pass

        def send_data(self, code, data, mime):
            self.send_response(code)
            for key, value in {
                "Content-Type": mime, "Content-Length": str(len(data)),
                "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer", "Content-Security-Policy": CSP,
            }.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(data)

        def reply(self, code, data):
            self.send_data(code, json.dumps(data, ensure_ascii=True).encode("utf-8"), "application/json; charset=utf-8")

        def authorized(self):
            supplied = self.headers.get("X-Workspace-Token", "")
            return supplied.isascii() and secrets.compare_digest(supplied, token)

        def do_GET(self):
            if self.headers.get("Host") != host:
                self.reply(403, {"error": "Invalid host"})
                return
            try:
                if len(self.path) > 2048:
                    raise ValueError("Request exceeds limit")
                parsed = urlsplit(self.path)
                if parsed.scheme or parsed.netloc or parsed.fragment:
                    raise ValueError("Invalid route")
                if parsed.path in ROUTES and not parsed.query:
                    name, mime = ROUTES[parsed.path]
                    self.send_data(200, (root / name).read_bytes(), mime)
                elif parsed.path == "/api/session" and not parsed.query:
                    self.reply(200, {"token": token, "config": config})
                elif parsed.path == "/api/records":
                    if not self.authorized():
                        self.reply(403, {"error": "Invalid session"})
                        return
                    query = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=1)
                    if set(query) != {"table"} or len(query["table"]) != 1:
                        raise ValueError("Choose one table")
                    self.reply(200, records_response(db_path, schema, query["table"][0]))
                else:
                    self.reply(404, {"error": "Not found"})
            except (ValueError, OSError, sqlite3.Error, TypeError):
                self.reply(400, {"error": "Unable to read workspace; check the table and database"})

        def do_POST(self):
            if self.headers.get("Host") != host or self.headers.get("Origin") != origin or not self.authorized():
                self.reply(403, {"error": "Invalid session"})
                return
            if self.path != "/api/records":
                self.reply(404, {"error": "Not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "-1"))
                if self.headers.get_content_type() != "application/json" or not 0 < length <= 16384:
                    raise ValueError("Invalid request")
                payload = json.loads(self.rfile.read(length).decode("utf-8"), object_pairs_hook=rel.unique_object,
                                     parse_constant=rel.reject_constant)
                self.reply(200, mutation(db_path, schema, payload))
            except (ValueError, OSError, sqlite3.Error, TypeError):
                self.reply(400, {"error": "Unable to update record; check fields and relationships"})

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8768)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Choose a port from 1024 to 65535")
    try:
        with ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.port, secrets.token_urlsafe(32))) as server:
            print(f"Local relational workspace: http://127.0.0.1:{args.port}")
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
