"""Export an independently authored local SQLite workspace."""
import argparse
import io
import json
from pathlib import Path
import zipfile

try:
    from .creator_project import require_text
except ImportError:
    from creator_project import require_text

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "fullstack"
FILES = ("server.py", "index.html", "style.css", "app.js")


def export_fullstack(title, description):
    config = {"title": require_text(title, "Title", 120),
              "description": require_text(description, "Description", 1000)}
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.writestr(name, (TEMPLATE / name).read_bytes())
        archive.writestr("config.json", json.dumps(config, indent=2) + "\n")
        archive.writestr("README.md", "# Local workspace\n\nRun python server.py, then open the printed loopback address. Python 3.10+ only. Data is saved in workspace.sqlite3. Back up the database while the server is stopped. Local single-user prototype only: no public hosting, user accounts, or internet exposure.\n")
        archive.writestr(".gitignore", "*.sqlite3\n*.sqlite3-*\n__pycache__/\n")
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = export_fullstack(args.title, args.description)
    with args.output.open("xb") as stream:
        stream.write(data)


if __name__ == "__main__":
    main()
