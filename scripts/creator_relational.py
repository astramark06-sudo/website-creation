"""Bounded local relational schema engine; no HTTP service or external dependencies."""
from __future__ import annotations

import argparse
from contextlib import closing, contextmanager
import json
import os
from pathlib import Path
import re
import sqlite3

# Standalone validation so the same engine can run inside an exported application.
def require_text(value, label, limit):
    if (not isinstance(value, str) or not value.strip() or len(value) > limit
            or any(ord(c) < 32 and c not in "\t\n\r" or 0xD800 <= ord(c) <= 0xDFFF for c in value)):
        raise ValueError(f"Invalid {label}")
    return value.strip()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError("Non-finite JSON number")

LIMIT = 1000
MAX_ID = 2**53 - 1  # Exact round-trip through a future JavaScript client.
IDENTIFIER = re.compile(r"[a-z][a-z0-9_]{0,31}\Z")


def identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError("Invalid schema identifier")
    return value


def validate_schema(schema):
    if not isinstance(schema, dict) or set(schema) != {"version", "tables"}:
        raise ValueError("Invalid relational schema")
    if type(schema["version"]) is not int or schema["version"] != 1:
        raise ValueError("Unsupported schema version")
    tables = schema["tables"]
    if not isinstance(tables, list) or not 2 <= len(tables) <= 4:
        raise ValueError("Use 2 to 4 tables")
    ids = set()
    relations = []
    for table in tables:
        if not isinstance(table, dict) or set(table) != {"id", "label", "fields"}:
            raise ValueError("Invalid table definition")
        name = identifier(table["id"])
        if name in ids:
            raise ValueError("Duplicate table")
        ids.add(name)
        require_text(table["label"], "Table label", 80)
        fields = table["fields"]
        if not isinstance(fields, list) or not 1 <= len(fields) <= 8:
            raise ValueError("Use 1 to 8 fields per table")
        seen = set()
        for field in fields:
            if not isinstance(field, dict):
                raise ValueError("Invalid field definition")
            kind = field.get("type")
            if kind not in ("text", "integer", "choice", "relation"):
                raise ValueError("Unsupported field type")
            keys = {"id", "label", "type"} | ({"choices"} if kind == "choice" else {"target"} if kind == "relation" else set())
            if set(field) != keys:
                raise ValueError("Invalid field definition")
            key = identifier(field["id"])
            if key in seen or key == "id":
                raise ValueError("Duplicate or reserved field")
            seen.add(key)
            require_text(field["label"], "Field label", 80)
            if kind == "choice":
                choices = field["choices"]
                if not isinstance(choices, list) or not 1 <= len(choices) <= 12:
                    raise ValueError("Use 1 to 12 choices")
                for choice in choices:
                    require_text(choice, "Choice", 80)
                if len(set(choices)) != len(choices):
                    raise ValueError("Duplicate choice")
            if kind == "relation":
                target = identifier(field["target"])
                if target == name:
                    raise ValueError("Relations must target another table")
                relations.append(target)
    if not set(relations) <= ids:
        raise ValueError("Unknown relation target")
    # Round-trip to detach validated definitions from caller-owned mutable objects.
    serialized = canonical(schema)
    if len(serialized.encode('utf-8')) > 32768:
        raise ValueError('Schema exceeds 32 KiB')
    return json.loads(serialized)


def canonical(schema):
    return json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def read_schema(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(32769)
    if len(raw) > 32768:
        raise ValueError("Schema exceeds 32 KiB")
    return validate_schema(json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=reject_constant))


def table_sql(name):
    return '"t_' + identifier(name) + '"'


def field_sql(name):
    return '"f_' + identifier(name) + '"'


def table_definition(schema, table):
    table = next((item for item in schema["tables"] if item["id"] == table), None)
    if table is None:
        raise ValueError("Unknown table")
    return table


def create_database(path, schema):
    """Create a new database only; never reinterpret an existing database."""
    schema = validate_schema(schema)
    path = Path(path)
    if path.suffix != ".sqlite3":
        raise ValueError("Use a .sqlite3 filename")
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE")
            db.execute("CREATE TABLE schema_info (id INTEGER PRIMARY KEY CHECK(id=1), definition TEXT NOT NULL)")
            db.execute("INSERT INTO schema_info VALUES (1,?)", (canonical(schema),))
            for table in schema["tables"]:
                columns = ["id INTEGER PRIMARY KEY AUTOINCREMENT CHECK(id BETWEEN 1 AND 9007199254740991)"]
                for field in table["fields"]:
                    col = field_sql(field["id"])
                    kind = field["type"]
                    if kind == "integer":
                        columns.append(col + " INTEGER NOT NULL CHECK(typeof(" + col + ")='integer' AND " + col + " BETWEEN 0 AND 1000000)")
                    elif kind == "relation":
                        columns.append(col + " INTEGER REFERENCES " + table_sql(field["target"]) + "(id) ON DELETE SET NULL")
                    else:
                        bound = 80 if kind == "choice" else 160
                        columns.append(col + " TEXT NOT NULL CHECK(length(" + col + ")<=" + str(bound) + ")")
                db.execute("CREATE TABLE " + table_sql(table["id"]) + " (" + ", ".join(columns) + ")")
            for table in schema["tables"]:
                for field in table["fields"]:
                    if field["type"] == "relation":
                        # Index names use a length-delimited table identifier to avoid collisions.
                        idx = '"idx_' + str(len(table["id"])) + '_' + table["id"] + '_' + field["id"] + '"'
                        db.execute("CREATE INDEX " + idx + " ON " + table_sql(table["id"]) + "(" + field_sql(field["id"]) + ")")
            if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise ValueError("Invalid relationships")
    except BaseException:
        path.unlink()
        raise
    return path


@contextmanager
def connect(path, schema, write=False):
    schema = validate_schema(schema)
    mode = "rw" if write else "ro"
    uri = Path(path).resolve().as_uri() + "?mode=" + mode
    with closing(sqlite3.connect(uri, uri=True, timeout=5)) as db, db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        row = db.execute("SELECT definition FROM schema_info WHERE id=1").fetchone()
        if row is None or row[0] != canonical(schema):
            raise ValueError("Database schema mismatch")
        yield db, schema


def record_id(value):
    if type(value) is not int or not 1 <= value <= MAX_ID:
        raise ValueError("Invalid record ID")
    return value


def validate_values(db, table, values):
    fields = table["fields"]
    if not isinstance(values, dict) or set(values) != {f["id"] for f in fields}:
        raise ValueError("Provide exactly the declared fields")
    result = []
    for field in fields:
        value = values[field["id"]]
        kind = field["type"]
        if kind == "integer":
            if type(value) is not int or not 0 <= value <= 1000000:
                raise ValueError("Expected an integer from 0 to 1000000")
        elif kind == "text":
            if not isinstance(value, str) or len(value) > 160 or any(ord(c) < 32 and c not in "\t\n\r" or 0xD800 <= ord(c) <= 0xDFFF for c in value):
                raise ValueError("Invalid text")
        elif kind == "choice":
            if not isinstance(value, str) or value not in field["choices"]:
                raise ValueError("Unknown choice")
        elif value is not None:
            record_id(value)
            if db.execute("SELECT 1 FROM " + table_sql(field["target"]) + " WHERE id=?", (value,)).fetchone() is None:
                raise ValueError("Related record does not exist")
        result.append(value)
    return result


def records_in_transaction(db, schema, table):
    definition = table_definition(schema, table)
    fields = definition["fields"]
    sql = "SELECT id," + ",".join(field_sql(f["id"]) for f in fields) + " FROM " + table_sql(table) + " ORDER BY id LIMIT ?"
    rows = db.execute(sql, (LIMIT + 1,)).fetchall()
    if len(rows) > LIMIT:
        raise ValueError("Table exceeds record limit")
    result = []
    for row in rows:
        values = {field["id"]: row[i+1] for i, field in enumerate(fields)}
        validate_values(db, definition, values)
        result.append({"id": record_id(row[0]), "values": values})
    return result


def list_records(path, schema, table):
    with connect(path, schema) as (db, checked):
        return records_in_transaction(db, checked, table)


def add_record(path, schema, table, values):
    with connect(path, schema, write=True) as (db, checked):
        definition = table_definition(checked, table)
        data = validate_values(db, definition, values)
        target = table_sql(table)
        if db.execute("SELECT count(*) FROM " + target).fetchone()[0] >= LIMIT:
            raise ValueError("Table record limit reached")
        columns = ",".join(field_sql(f["id"]) for f in definition["fields"])
        placeholders = ",".join("?" for _ in data)
        cursor = db.execute("INSERT INTO " + target + "(" + columns + ") VALUES (" + placeholders + ")", data)
        return record_id(cursor.lastrowid)


def edit_record(path, schema, table, item_id, values):
    record_id(item_id)
    with connect(path, schema, write=True) as (db, checked):
        definition = table_definition(checked, table)
        data = validate_values(db, definition, values)
        assignments = ",".join(field_sql(f["id"]) + "=?" for f in definition["fields"])
        if db.execute("UPDATE " + table_sql(table) + " SET " + assignments + " WHERE id=?", (*data, item_id)).rowcount != 1:
            raise ValueError("Record not found")


def delete_record(path, schema, table, item_id):
    record_id(item_id)
    with connect(path, schema, write=True) as (db, checked):
        table_definition(checked, table)
        if db.execute("DELETE FROM " + table_sql(table) + " WHERE id=?", (item_id,)).rowcount != 1:
            raise ValueError("Record not found")


def migration_plan(old_schema, new_schema, defaults):
    """Accept only appended tables and fields with explicit scalar defaults."""
    old, new = validate_schema(old_schema), validate_schema(new_schema)
    if len(new["tables"]) < len(old["tables"]):
        raise ValueError("Cannot remove tables")
    added = {}
    for previous, extended in zip(old["tables"], new["tables"]):
        fields = previous["fields"]
        if (previous["id"] != extended["id"] or previous["label"] != extended["label"]
                or extended["fields"][:len(fields)] != fields):
            raise ValueError("Existing tables and fields must remain unchanged and in order")
        appended = extended["fields"][len(fields):]
        if appended:
            added[previous["id"]] = appended
    new_tables = len(new["tables"]) - len(old["tables"])
    if not added and not new_tables:
        raise ValueError("Migration must add fields or tables")
    if not isinstance(defaults, dict) or set(defaults) != set(added):
        raise ValueError("Provide defaults for exactly the tables with appended fields")
    for name, fields in added.items():
        values = defaults[name]
        if not isinstance(values, dict) or set(values) != {f["id"] for f in fields}:
            raise ValueError("Provide exactly one default per appended field")
        for field in fields:
            if field["type"] == "relation" and values[field["id"]] is not None:
                raise ValueError("New relation fields must default to null")
        validate_values(None, {"fields": fields}, values)
    return old, new, {"tables_added": new_tables, "fields_added": sum(map(len, added.values()))}


def verify_integrity(db):
    if [row[0] for row in db.execute("PRAGMA integrity_check")] != ["ok"]:
        raise ValueError("Database integrity check failed")
    if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("Database relationship integrity check failed")


def sequences(db, schema, records):
    names = {"t_" + table["id"]: table["id"] for table in schema["tables"]}
    result = {}
    for row in db.execute("SELECT name,seq FROM sqlite_sequence"):
        if row[0] not in names or names[row[0]] in result or type(row[1]) is not int or not 0 <= row[1] <= MAX_ID:
            raise ValueError("Invalid database ID sequence")
        result[names[row[0]]] = row[1]
    for name, items in records.items():
        if items and result.get(name, 0) < max(item["id"] for item in items):
            raise ValueError("Database ID sequence is inconsistent")
    return result


def migrate_database(source, destination, old_schema, new_schema, defaults):
    """Rebuild into a new verified database from one read-only source snapshot."""
    old, new, report = migration_plan(old_schema, new_schema, defaults)
    source, destination = Path(source), Path(destination)
    # All reads share a single SQLite transaction, even for cyclic relations.
    with connect(source, old) as (db, checked):
        verify_integrity(db)
        records = {t["id"]: records_in_transaction(db, checked, t["id"]) for t in old["tables"]}
        old_sequences = sequences(db, old, records)
    expected = {}
    for table in new["tables"]:
        name = table["id"]
        expected[name] = [
            {"id": row["id"], "values": {**row["values"], **defaults.get(name, {})}}
            for row in records.get(name, [])
        ]
    # Exclusive creation is outside cleanup: a pre-existing destination is never removed.
    create_database(destination, new)
    try:
        with connect(destination, new, write=True) as (db, checked):
            db.execute("PRAGMA defer_foreign_keys=ON")
            for table in new["tables"]:
                name = table["id"]
                fields = table["fields"]
                columns = "id," + ",".join(field_sql(f["id"]) for f in fields)
                placeholders = ",".join("?" for _ in range(len(fields) + 1))
                for row in expected[name]:
                    # Existing values and appended defaults were validated above.
                    db.execute("INSERT INTO " + table_sql(name) + "(" + columns + ") VALUES (" + placeholders + ")",
                               (row["id"], *(row["values"][f["id"]] for f in fields)))
                if name in old_sequences:
                    db.execute("DELETE FROM sqlite_sequence WHERE name=?", ("t_" + name,))
                    db.execute("INSERT INTO sqlite_sequence(name,seq) VALUES (?,?)", ("t_" + name, old_sequences[name]))
            verify_integrity(db)
        with connect(destination, new) as (db, checked):
            actual = {t["id"]: records_in_transaction(db, checked, t["id"]) for t in new["tables"]}
            if actual != expected or sequences(db, new, actual) != old_sequences:
                raise ValueError("Migrated records or ID sequences differ from source")
            verify_integrity(db)
    except BaseException:
        destination.unlink()
        raise
    return {**report, "records": sum(map(len, records.values()))}


def read_defaults(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(32769)
    if len(raw) > 32768:
        raise ValueError("Defaults exceed 32 KiB")
    defaults = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=reject_constant)
    if not isinstance(defaults, dict):
        raise ValueError("Expected a defaults object")
    return defaults


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        schema = read_schema(args.schema)
        create_database(args.output, schema)
        print(json.dumps({"status": "created", "tables": len(schema["tables"]), "records": 0}))
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
