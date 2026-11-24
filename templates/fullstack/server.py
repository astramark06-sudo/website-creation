"""Original local-only data workspace. Not a public multi-user server."""
import argparse
import json
import os
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
    if not isinstance(fields, list) or len(fields) > 8:
        raise ValueError("Invalid field definitions")
    seen = set()
    workflow_count = 0
    for field in fields:
        if not isinstance(field, dict):
            raise ValueError("Invalid field")
        kind = field.get("type")
        keys = {"id", "label", "type"} | ({"choices"} if kind in ("choice", "stage") else set())
        if set(field) != keys or kind not in ("integer", "text", "choice", "link", "stage"):
            raise ValueError("Invalid field type")
        name, label = field["id"], field["label"]
        if (not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", name)
                or name in seen or not isinstance(label, str) or not label.strip() or len(label) > 80):
            raise ValueError("Invalid or duplicate field")
        seen.add(name)
        if kind == "stage":
            workflow_count += 1
            if workflow_count > 1:
                raise ValueError("Only one workflow stage field is supported")
        if kind in ("choice", "stage"):
            options = field["choices"]
            if (not isinstance(options, list) or not (2 if kind == "stage" else 1) <= len(options) <= 12
                    or any(not isinstance(v, str) or not v.strip() or len(v) > 80 for v in options)
                    or len(set(options)) != len(options)):
                raise ValueError("Invalid choices")
    return fields


def split_details(fields, details, db=None, item_id=None):
    if not isinstance(details, dict) or set(details) != {f["id"] for f in fields}:
        raise ValueError("Missing or unknown model fields")
    scalar, links = {}, {}
    for field in fields:
        name, kind, value = field["id"], field["type"], details[field["id"]]
        if kind == "integer":
            if type(value) is not int or not 0 <= value <= 1000000:
                raise ValueError("Use an integer from 0 to 1000000")
            scalar[name] = value
        elif kind == "text":
            if not isinstance(value, str) or len(value) > 160:
                raise ValueError("Text field exceeds limit")
            scalar[name] = value
        elif kind in ("choice", "stage"):
            if not isinstance(value, str) or value not in field["choices"]:
                raise ValueError("Unknown choice")
            scalar[name] = value
        else:
            if value is not None and (type(value) is not int or not 1 <= value <= 2**63 - 1):
                raise ValueError("Invalid linked record")
            if value is not None and item_id == value:
                raise ValueError("A record cannot link to itself")
            if value is not None and db is not None and db.execute(
                    "SELECT 1 FROM items WHERE id=?", (value,)).fetchone() is None:
                raise ValueError("Linked record not found")
            links[name] = value
    return scalar, links


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
            db.execute("CREATE TABLE IF NOT EXISTS item_links (item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE, field_id TEXT NOT NULL, target_id INTEGER REFERENCES items(id) ON DELETE SET NULL, PRIMARY KEY(item_id,field_id))")
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


def link_options(path, fields=None):
    with closing(database(path, fields)) as db:
        return [dict(row) for row in db.execute("SELECT id,title FROM items ORDER BY title COLLATE NOCASE,id LIMIT ?", (LIMIT,))]


def list_items(path, query="", state="all", fields=None, stage=None):
    fields = validate_fields([] if fields is None else fields)
    if not isinstance(query, str) or state not in ("all", "open", "done") or len(query) > 200:
        raise ValueError("Invalid filter")
    workflow = next((f for f in fields if f["type"] == "stage"), None)
    if stage is not None and (not workflow or stage not in workflow["choices"]):
        raise ValueError("Invalid workflow stage filter")
    scalar_ids = {f["id"] for f in fields if f["type"] != "link"}
    link_ids = {f["id"] for f in fields if f["type"] == "link"}
    with closing(database(path, fields)) as db:
        # Read records and relationships from one consistent snapshot.
        db.execute("BEGIN")
        rows = db.execute(
            "SELECT items.id,title,notes,done,item_details.data FROM items "
            "LEFT JOIN item_details ON item_details.item_id=items.id "
            "WHERE (?='all' OR done=?) ORDER BY items.id DESC LIMIT ?",
            (state, int(state == "done"), LIMIT),
        ).fetchall()
        linked = {}
        if link_ids:
            for row in db.execute(
                    "SELECT item_links.item_id,field_id,target_id,items.title AS target_title "
                    "FROM item_links LEFT JOIN items ON items.id=item_links.target_id"):
                linked[(row["item_id"], row["field_id"])] = (
                    None if row["target_id"] is None
                    else {"id": row["target_id"], "title": row["target_title"]}
                )
        result = []
        for row in rows:
            item = {k: row[k] for k in ("id", "title", "notes", "done")}
            values = []
            if fields:
                scalar = json.loads(row["data"] or "{}")
                if not isinstance(scalar, dict) or set(scalar) != scalar_ids:
                    raise ValueError("Stored model data does not match the configured schema")
                item["details"] = {}
                item["links"] = {}
                for field in fields:
                    name = field["id"]
                    if field["type"] == "link":
                        target = linked.get((row["id"], name))
                        item["details"][name] = None if target is None else target["id"]
                        item["links"][name] = target
                        if target is not None:
                            values.append(target["title"])
                    else:
                        # Reuse validation for each scalar field through a temporary full object later.
                        item["details"][name] = scalar[name]
                        values.append(str(scalar[name]))
                split_details(fields, item["details"], db, item["id"])
            if stage is not None and item["details"][workflow["id"]] != stage:
                continue
            if not query or any(query.casefold() in value.casefold()
                                for value in [item["title"], item["notes"], *values]):
                result.append(item)
        return result


def summarize_items(items, fields=None):
    """Describe the same filtered, bounded records returned to the workspace."""
    fields = validate_fields([] if fields is None else fields)
    total = len(items)
    completed = sum(item["done"] == 1 for item in items)
    metrics = []
    for field in fields:
        name, kind = field["id"], field["type"]
        values = [item["details"][name] for item in items]
        metric = {"id": name, "label": field["label"], "type": kind}
        if kind == "integer":
            metric.update(total=sum(values), average=round(sum(values) / total, 2) if total else None)
        elif kind in ("choice", "stage"):
            metric["choices"] = [{"label": choice, "count": values.count(choice)}
                                 for choice in field["choices"]]
        elif kind == "link":
            metric.update(linked=sum(value is not None for value in values))
        else:
            continue
        metrics.append(metric)
    return {"total": total, "completed": completed, "open": total - completed,
            "completion_percent": round(100 * completed / total, 1) if total else None,
            "fields": metrics}


def change_item(path, payload, fields=None):
    fields = validate_fields([] if fields is None else fields)
    if not isinstance(payload, dict):
        raise ValueError("Expected object")
    action = payload.get("action")
    keys = {"add": {"action", "title", "notes"}, "edit": {"action", "id", "title", "notes"},
            "toggle": {"action", "id"}, "delete": {"action", "id"}}
    workflow = next((f for f in fields if f["type"] == "stage"), None)
    if workflow:
        keys["move_stage"] = {"action", "id", "expected", "target"}
    if fields:
        keys["add"].add("details")
        keys["edit"].add("details")
    if not isinstance(action, str) or action not in keys or set(payload) != keys[action]:
        raise ValueError("Invalid action")
    if action in ("add", "edit"):
        title, notes = payload["title"], payload["notes"]
        if not isinstance(title, str) or not title.strip() or len(title) > 160 or not isinstance(notes, str) or len(notes) > 2000:
            raise ValueError("Invalid title or notes")
    if action != "add" and (type(payload["id"]) is not int or not 1 <= payload["id"] <= 2**63 - 1):
        raise ValueError("Invalid item id")
    with closing(database(path, fields)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        item_id = payload.get("id")
        scalar, links = split_details(fields, payload.get("details", {}), db, item_id) if action in ("add", "edit") else ({}, {})
        if workflow and action in ("add", "edit", "move_stage"):
            name, stages = workflow["id"], workflow["choices"]
            if action == "add":
                if scalar[name] != stages[0]:
                    raise ValueError("New records must start at the first stage")
            else:
                row = db.execute("SELECT data FROM item_details WHERE item_id=?", (item_id,)).fetchone()
                if row is None:
                    raise ValueError("Item not found")
                previous = json.loads(row[0])
                if not isinstance(previous, dict):
                    raise ValueError("Invalid stored workflow data")
                current = previous.get(name)
                if current not in stages:
                    raise ValueError("Invalid stored workflow stage")
                if action == "edit" and scalar[name] != current:
                    raise ValueError("Use the workflow controls to change stages")
                if action == "move_stage":
                    target = payload["target"]
                    if not isinstance(target, str) or not isinstance(payload["expected"], str) or payload["expected"] != current or target not in stages or abs(stages.index(target) - stages.index(current)) != 1:
                        raise ValueError("Invalid or stale workflow transition")
                    previous[name] = target
                    db.execute("UPDATE item_details SET data=? WHERE item_id=?",
                               (json.dumps(previous, ensure_ascii=False, sort_keys=True), item_id))
                    return
        if action == "add":
            if db.execute("SELECT count(*) FROM items").fetchone()[0] >= LIMIT:
                raise ValueError("Item limit reached")
            item_id = db.execute("INSERT INTO items(title,notes) VALUES (?,?)", (title.strip(), notes)).lastrowid
        elif action == "edit":
            result = db.execute("UPDATE items SET title=?,notes=? WHERE id=?", (title.strip(), notes, item_id))
        elif action == "toggle":
            result = db.execute("UPDATE items SET done=1-done WHERE id=?", (item_id,))
        else:
            result = db.execute("DELETE FROM items WHERE id=?", (item_id,))
        if action != "add" and result.rowcount != 1:
            raise ValueError("Item not found")
        if fields and action in ("add", "edit"):
            db.execute("INSERT INTO item_details(item_id,data) VALUES (?,?) "
                       "ON CONFLICT(item_id) DO UPDATE SET data=excluded.data",
                       (item_id, json.dumps(scalar, ensure_ascii=False, sort_keys=True)))
            db.execute("DELETE FROM item_links WHERE item_id=?", (item_id,))
            for field_id, target_id in links.items():
                if target_id is not None:
                    db.execute("INSERT INTO item_links(item_id,field_id,target_id) VALUES (?,?,?)",
                               (item_id, field_id, target_id))


def backup_database(source, destination, fields=None):
    """Create a checked SQLite snapshot at a new local path, never overwrite."""
    source, destination = Path(source), Path(destination)
    if not source.is_file():
        raise ValueError("No existing workspace database to back up")
    if destination.suffix != ".sqlite3":
        raise ValueError("Use a .sqlite3 backup filename")
    # SQLite's backup API copies a consistent snapshot, including committed
    # transactions in the journal. Validate the model before creating output.
    with closing(database(source, fields)) as original:
        if [row[0] for row in original.execute("PRAGMA quick_check")] != ["ok"]:
            raise ValueError("Source database failed integrity check")
        if original.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("Source database has invalid relationships")
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        try:
            with closing(sqlite3.connect(destination, timeout=5)) as target:
                original.backup(target)
                if target.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise ValueError("Backup integrity check failed")
                if target.execute("PRAGMA foreign_key_check").fetchone() is not None:
                    raise ValueError("Backup relationship check failed")
        except BaseException:
            destination.unlink()
            raise
    return destination


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
                    params = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=3)
                    if set(params) - {"q", "state", "stage"} or any(len(v) != 1 for v in params.values()):
                        raise ValueError("Invalid filters")
                    items = list_items(db_path, params.get("q", [""])[0], params.get("state", ["all"])[0], fields, params.get("stage", [None])[0])
                    self.reply(200, {
                        "items": items,
                        "summary": summarize_items(items, fields),
                        "link_options": link_options(db_path, fields) if any(f["type"] == "link" for f in fields) else [],
                    })
                else:
                    self.reply(404, {"error": "Not found"})
            except (ValueError, OSError, sqlite3.Error, json.JSONDecodeError):
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
            except (ValueError, OSError, sqlite3.Error, json.JSONDecodeError):
                self.reply(400, {"error": "Unable to update item; check fields and limits"})

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--backup", type=Path, help="Create a checked, new local SQLite snapshot and exit")
    args = parser.parse_args()
    if args.backup is not None:
        try:
            config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
            saved = backup_database(ROOT / "workspace.sqlite3", args.backup, config.get("fields", []))
            print(f"Backup created: {saved}. Keep a matching copy of config.json.")
        except (ValueError, OSError, sqlite3.Error) as exc:
            parser.error(str(exc))
        return
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
