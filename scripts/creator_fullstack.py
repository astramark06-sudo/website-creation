"""Export an independently authored local SQLite workspace."""
import argparse
import io
import json
from pathlib import Path
import re
import zipfile

try:
    from .creator_project import require_text
except ImportError:
    from creator_project import require_text

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "fullstack"
FILES = ("server.py", "index.html", "style.css", "app.js")
FIELD_ID = re.compile(r"[a-z][a-z0-9_]{0,31}\Z")
MODELS = {
    "records": [],
    "inventory": [{"id": "quantity", "label": "Quantity", "type": "integer"},
                  {"id": "location", "label": "Storage location", "type": "text"}],
    "issues": [{"id": "priority", "label": "Priority", "type": "choice", "choices": ["Low", "Normal", "High"]},
               {"id": "category", "label": "Category", "type": "text"}],
    "reading": [{"id": "pages", "label": "Pages", "type": "integer"},
                {"id": "format", "label": "Format", "type": "choice", "choices": ["Print", "Digital", "Audio"]}],
}


def validate_fields(fields, require_nonempty=False):
    if not isinstance(fields, list) or len(fields) > 8 or (require_nonempty and not fields):
        raise ValueError("Custom schemas require 1 to 8 fields")
    seen = set()
    workflow_count = 0
    for field in fields:
        if not isinstance(field, dict):
            raise ValueError("Invalid field")
        kind = field.get("type")
        keys = {"id", "label", "type"} | ({"choices"} if kind in ("choice", "stage") else set())
        if set(field) != keys or kind not in ("integer", "text", "choice", "link", "stage"):
            raise ValueError("Unsupported field type")
        name, label = field["id"], field["label"]
        if (not isinstance(name, str) or not FIELD_ID.fullmatch(name) or name in seen
                or not isinstance(label, str) or not label.strip() or len(label) > 80):
            raise ValueError("Invalid or duplicate field")
        seen.add(name)
        if kind == "stage":
            workflow_count += 1
            if workflow_count > 1:
                raise ValueError("Only one workflow stage field is supported")
        if kind in ("choice", "stage"):
            choices = field["choices"]
            if (not isinstance(choices, list) or not (2 if kind == "stage" else 1) <= len(choices) <= 12
                    or any(not isinstance(v, str) or not v.strip() or len(v) > 80 for v in choices)
                    or len(set(choices)) != len(choices)):
                raise ValueError("Invalid choices")
    return fields


def export_fullstack(title, description, model="records", fields=None):
    if not isinstance(model, str) or model not in (*MODELS, "custom"):
        raise ValueError("Unsupported data model")
    if model == "custom":
        schema = validate_fields(fields, require_nonempty=True)
    else:
        if fields not in (None, []):
            raise ValueError("Custom fields are only accepted for the custom model")
        schema = validate_fields(MODELS[model])
    config = {"title": require_text(title, "Title", 120),
              "description": require_text(description, "Description", 1000)}
    if model != "records":
        config.update(model=model, fields=schema)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.writestr(name, (TEMPLATE / name).read_bytes())
        archive.writestr("config.json", json.dumps(config, indent=2) + "\n")
        archive.writestr(
            "README.md",
            "# Local workspace\n\nRun python server.py, then open the printed loopback address. "
            "Python 3.10+ only. Data is saved in workspace.sqlite3. Stop the server, then run python server.py --backup snapshot.sqlite3. "
            "Keep backups private. Local single-user prototype only: no public hosting, user "
            "accounts, or internet exposure. Keep config.json with its matching database.\n",
        )
        archive.writestr(".gitignore", "*.sqlite3\n*.sqlite3-*\n__pycache__/\n")
    return output.getvalue()


def read_schema(path):
    data = path.read_bytes()
    if len(data) > 32 * 1024:
        raise ValueError("Schema exceeds 32 KiB")
    return validate_fields(json.loads(data.decode("utf-8")), require_nonempty=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", choices=(*MODELS, "custom"), default="records")
    parser.add_argument("--schema", type=Path, help="JSON field array; required only for --model custom")
    args = parser.parse_args()
    try:
        if (args.model == "custom") != (args.schema is not None):
            raise ValueError("--schema is required only with --model custom")
        fields = read_schema(args.schema) if args.schema else None
        data = export_fullstack(args.title, args.description, args.model, fields)
        with args.output.open("xb") as stream:
            stream.write(data)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
