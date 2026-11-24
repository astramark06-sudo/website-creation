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
    from .creator_project import MAX_SPEC, assemble, build, read_spec, validate_spec, spec_bytes, unique_object, reject_constant
    from .creator_reference import reference_plan
    from .creator_ai import generate_draft, valid_model
    from .creator_vision import vision_plan
    from .creator_fullstack import export_fullstack
    from .creator_relational_export import export_relational
    from .creator_authenticated_export import export_authenticated
    from .creator_authenticated_check import check_authenticated
    from .creator_relational import validate_schema
    from .creator_relational_check import check_relational
    from .creator_tools import overview, query_tool, propose_plan
    from .creator_release import release_report
    from .creator_browser import check_browser
    from .creator_visual_reference import visual_plan
except ImportError:
    from creator_project import MAX_SPEC, assemble, build, read_spec, validate_spec, spec_bytes, unique_object, reject_constant
    from creator_reference import reference_plan
    from creator_ai import generate_draft, valid_model
    from creator_vision import vision_plan
    from creator_fullstack import export_fullstack
    from creator_relational_export import export_relational
    from creator_authenticated_export import export_authenticated
    from creator_authenticated_check import check_authenticated
    from creator_relational import validate_schema
    from creator_relational_check import check_relational
    from creator_tools import overview, query_tool, propose_plan
    from creator_release import release_report
    from creator_browser import check_browser
    from creator_visual_reference import visual_plan

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
    return page.replace('<script src="app.js" defer></script>', "").replace('<script src="search.js" defer></script>', "").replace('href="', 'data-preview-href="')


def export_zip(spec):
    draft = draft_spec(spec)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "site"
        build(draft, out)
        result = io.BytesIO()
        with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(out.iterdir()):
                archive.write(path, "site/" + path.name)
            archive.writestr("project.json", spec_bytes(draft))
        return result.getvalue()


def make_handler(port, token, ai_model=None, browser_checks=False, vision_model=None):
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
                      "/studio.js": ("studio.js", "text/javascript; charset=utf-8"),
                      "/visual-reference.js": ("visual-reference.js", "text/javascript; charset=utf-8"),
                      "/relational-designer.js": ("relational-designer.js", "text/javascript; charset=utf-8")}
            if self.path == "/api/session":
                self.send_json(200, {"token": token, "project": read_spec(ROOT / "projects" / "example.json"), "ai_enabled": ai_model is not None, "vision_enabled": vision_model is not None, "browser_checks_enabled": browser_checks})
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
            if self.path not in ("/api/preview", "/api/export", "/api/reference", "/api/ai-draft", "/api/fullstack-export", "/api/relational-export", "/api/authenticated-export", "/api/relational-validate", "/api/relational-check", "/api/authenticated-check", "/api/tool-query", "/api/tool-plan", "/api/tool-overview", "/api/release-report", "/api/browser-check", "/api/visual-reference", "/api/vision-reference"):
                self.send_json(404, {"error": "Not found"})
                return
            try:
                if self.headers.get_content_type() != "application/json":
                    raise ValueError("Expected JSON")
                length = int(self.headers.get("Content-Length", "-1"))
                # Allow the bounded JSON envelope around a maximum-size project.
                if not 0 < length <= MAX_SPEC + 4096:
                    raise ValueError("Invalid request size")
                payload = json.loads(self.rfile.read(length).decode("utf-8"),
                                     object_pairs_hook=unique_object, parse_constant=reject_constant)
                if not isinstance(payload, dict):
                    raise ValueError("Expected JSON object")
                if self.path == "/api/ai-draft":
                    if not ai_model:
                        self.send_json(403, {"error": "Local AI is not enabled"})
                        return
                    if payload.get("confirmed") is not True:
                        raise ValueError("Local AI consent required")
                    self.send_json(200, {"project": generate_draft(payload["prompt"], ai_model)})
                elif self.path == "/api/browser-check":
                    if not browser_checks:
                        self.send_json(403, {"error": "Browser checks are not enabled"})
                        return
                    if set(payload) not in ({"spec", "confirmed"}, {"spec", "confirmed", "engine"}) or payload.get("confirmed") is not True:
                        raise ValueError("Browser check consent required")
                    self.send_json(200, check_browser(draft_spec(payload["spec"]), engine=payload.get("engine", "chromium")))
                elif self.path == "/api/release-report":
                    self.send_json(200, release_report(draft_spec(payload["spec"])))
                elif self.path == "/api/tool-overview":
                    self.send_json(200, overview(port))
                elif self.path == "/api/tool-query":
                    self.send_json(200, query_tool(payload))
                elif self.path == "/api/tool-plan":
                    self.send_json(200, propose_plan(payload))
                elif self.path in ("/api/relational-check", "/api/authenticated-check"):
                    if not browser_checks:
                        self.send_json(403, {"error": "Browser checks are not enabled"})
                        return
                    if set(payload) != {"title", "description", "schema", "engine", "confirmed"} or payload["confirmed"] is not True:
                        raise ValueError("Explicit application check consent required")
                    verify = check_authenticated if self.path == "/api/authenticated-check" else check_relational
                    self.send_json(200, verify(payload["title"], payload["description"],
                                               payload["schema"], payload["engine"]))
                elif self.path == "/api/relational-validate":
                    if set(payload) != {"schema"}:
                        raise ValueError("Expected relational schema")
                    self.send_json(200, {"schema": validate_schema(payload["schema"])})
                elif self.path == "/api/authenticated-export":
                    if set(payload) != {"title", "description", "schema", "confirmed"} or payload["confirmed"] is not True:
                        raise ValueError("Explicit local staging export consent required")
                    data = export_authenticated(payload["title"], payload["description"], payload["schema"])
                    self.send_data(200, data, "application/zip", {"Content-Disposition": 'attachment; filename="authenticated-local-staging.zip"'})
                elif self.path == "/api/relational-export":
                    if set(payload) != {"title", "description", "schema"}:
                        raise ValueError("Invalid relational export fields")
                    data = export_relational(payload["title"], payload["description"], payload["schema"])
                    self.send_data(200, data, "application/zip", {"Content-Disposition": 'attachment; filename="local-relational-workspace.zip"'})
                elif self.path == "/api/fullstack-export":
                    data = export_fullstack(payload["title"], payload["description"], payload.get("model", "records"), payload.get("fields"))
                    self.send_data(200, data, "application/zip", {"Content-Disposition": 'attachment; filename="local-data-workspace.zip"'})
                elif self.path == "/api/vision-reference":
                    if not vision_model:
                        self.send_json(403, {"error": "Local vision is not enabled"})
                        return
                    if set(payload) != {"image", "title", "objective", "authorized"}:
                        raise ValueError("Invalid vision request")
                    self.send_json(200, vision_plan(payload["image"], payload["title"], payload["objective"],
                                                    payload["authorized"], vision_model))
                elif self.path == "/api/visual-reference":
                    self.send_json(200, visual_plan(payload["observations"], payload["title"], payload["objective"], payload["authorized"]))
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
    parser.add_argument("--vision-model", help="Opt in to an already installed local Ollama vision model")
    parser.add_argument("--browser-checks", action="store_true", help="Enable optional installed browser testing")
    args = parser.parse_args()
    if any(model and not valid_model(model) for model in (args.local_model, args.vision_model)):
        parser.error("Use a local model name, not a cloud model")
    if not 1024 <= args.port <= 65535:
        parser.error("Choose a port from 1024 to 65535")
    with ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.port, secrets.token_urlsafe(32), args.local_model, args.browser_checks, args.vision_model)) as server:
        print(f"Master Creator: http://127.0.0.1:{args.port} (local only)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
