"""Export a self-contained local relational application with no runtime packages."""
import argparse
import io
import json
from pathlib import Path
import zipfile

try:
    from .creator_relational import validate_schema, read_schema, require_text
except ImportError:
    from creator_relational import validate_schema, read_schema, require_text

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "relational"


def export_relational(title, description, schema):
    config = {"title": require_text(title, "title", 120),
              "description": require_text(description, "description", 1000),
              "schema": validate_schema(schema)}
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in ("server.py", "index.html", "app.js", "style.css"):
            archive.writestr(name, (TEMPLATE / name).read_bytes())
        archive.writestr("creator_relational.py", (ROOT / "scripts" / "creator_relational.py").read_bytes())
        archive.writestr("config.json", json.dumps(config, ensure_ascii=False, separators=(",", ":")))
        archive.writestr(".gitignore", "*.sqlite3\n*.sqlite3-*\n__pycache__/\n")
        archive.writestr("README.md", "# Local relational workspace\n\nRun python server.py with Python 3.10+ and open the printed loopback URL. "
                         "Create related records in their own tables, then select them from relation controls. "
                         "Deleting a record clears references to it. Keep your data private. "
                         "Stop the server before copying workspace.sqlite3 and config.json for backup. "
                         "Do not change the schema of an existing database or expose the server publicly. "
                         "No user accounts or production deployment support.\n")
    return result.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        data = export_relational(args.title, args.description, read_schema(args.schema))
        with args.output.open("xb") as stream:
            stream.write(data)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
