"""Local-only graphical workspace for the existing original-site generator."""
from __future__ import annotations

import argparse
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import secrets
import tempfile
import zipfile

try:
    from .creator_project import MAX_SPEC, assemble, build, read_spec, validate_spec
    from .creator_reference import reference_plan
    from .creator_ai import generate_draft, valid_model
except ImportError:
    from creator_project import MAX_SPEC, assemble, build, read_spec, validate_spec
    from creator_reference import reference_plan
    from creator_ai import generate_draft, valid_model

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "studio"
CSP = "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-src 'self' about:; img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"


def draft_spec(spec):
    validate_spec(spec)
    draft = copy.deepcopy(spec)
    draft["review"] = {key: False for key in draft["review"]}
    return draft


def preview_document(spec, slug):
    files = assemble(spec)
    if not any(p["slug"] == slug for p in spec["pages"]):
        raise ValueError("Unknown page")
    name = "index.html" if slug == "home" else slug + ".html"
    page = files[name].replace('<link rel="stylesheet" href="style.css">', "<style>" + files["style.css"] + "</style>")
    # The preview is inert: no scripts, navigable links or form submissions.
    return page.replace('<script src="app.js" defer></script>', "").replace('href="', 'data-preview-href="')


def export_zip(spec):
    draft = draft_spec(spec)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "site"
        build(draft, out)
        result = io.BytesIO()
        with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(out.iterdir()):
                archive.write(path, "site/" + path.name)
            archive.writestr("project.json", json.dumps(draft, indent=2) + "\n")
        return result.getvalue()


def make_handler(port, token, ai_model=None):
    host = f"127.0.0.1:{port}"
    origin = "http://" + host

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def send_data(self, code, body, mime, extra=None):
            self.send_response(code)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", CSP)
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, code, obj):
            self.send_data(code, json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8")

        def valid_host(self):
            if self.headers.get("Host") != host:
                self.send_json(403, {"error": "Invalid host"})
                return False
            return True

        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def do_GET(self):
            if not self.valid_host():
                return
            routes = {"/": ("index.html", "text/html; charset=utf-8"),
                      "/studio.css": ("studio.css", "text/css; charset=utf-8"),
                      "/studio.js": ("studio.js", "text/javascript; charset=utf-8")}
            if self.path == "/api/session":
                self.send_json(200, {"token": token, "project": read_spec(ROOT / "projects" / "example.json"), "ai_enabled": ai_model is not None})
            elif self.path in routes:
                name, mime = routes[self.path]
                self.send_data(200, (UI / name).read_bytes(), mime)
            else:
                self.send_json(404, {"error": "Not found"})

        def do_POST(self):
            if not self.valid_host():
                return
            if self.headers.get("Origin") != origin or not secrets.compare_digest(self.headers.get("X-Creator-Token", ""), token):
                self.send_json(403, {"error": "Local session required"})
                return
            if self.path not in ("/api/preview", "/api/export", "/api/reference", "/api/ai-draft"):
                self.send_json(404, {"error": "Not found"})
                return
            try:
                if self.headers.get_content_type() != "application/json":
                    raise ValueError("Expected JSON")
                length = int(self.headers.get("Content-Length", "-1"))
                if not 0 < length <= MAX_SPEC:
                    raise ValueError("Invalid request size")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if self.path == "/api/ai-draft":
                    if not ai_model:
                        self.send_json(403, {"error": "Local AI is not enabled"})
                        return
                    if payload.get("confirmed") is not True:
                        raise ValueError("Local AI consent required")
                    self.send_json(200, {"project": generate_draft(payload["prompt"], ai_model)})
                elif self.path == "/api/reference":
                    self.send_json(200, reference_plan(payload["source"], payload["title"], payload["objective"], payload["authorized"]))
                elif self.path == "/api/preview":
                    self.send_json(200, {"html": preview_document(payload["spec"], payload["slug"])})
                else:
                    data = export_zip(payload["spec"])
                    self.send_data(200, data, "application/zip", {"Content-Disposition": 'attachment; filename="creator-project.zip"'})
            except (ValueError, TypeError, KeyError, OSError, AttributeError):
                self.send_json(400, {"error": "Invalid project. Check required fields, unique page addresses and size limits."})

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--local-model", help="Opt in to an already installed offline Ollama model")
    args = parser.parse_args()
    if args.local_model and not valid_model(args.local_model):
        parser.error("Use a local model name, not a cloud model")
    if not 1024 <= args.port <= 65535:
        parser.error("Choose a port from 1024 to 65535")
    with ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.port, secrets.token_urlsafe(32), args.local_model)) as server:
        print(f"Master Creator: http://127.0.0.1:{args.port} (local only)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
