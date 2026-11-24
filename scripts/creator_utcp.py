"""Opt-in UTCP HTTP provider for read-only Master Creator discovery.

The native API exposes only repository-owned catalogue metadata and design
options. It never dispatches arbitrary commands or external provider calls.
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from urllib.parse import parse_qs, urlsplit

try:
    from .creator_build import THEMES
    from .creator_design import DESIGN_CHOICES, DEFAULT_DESIGN
    from .creator_plan import IMPORT_POLICY, load_catalog, search_sources, validate
except ImportError:
    from creator_build import THEMES
    from creator_design import DESIGN_CHOICES, DEFAULT_DESIGN
    from creator_plan import IMPORT_POLICY, load_catalog, search_sources, validate

VERSION = "1.1.0"
ROUTES = {
    "list_profiles": "/api/tools/profiles",
    "list_design_options": "/api/tools/design",
    "search_sources": "/api/tools/sources",
}


def manual(port):
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("Invalid port")
    origin = f"http://127.0.0.1:{port}"

    def tool(name, description, inputs, outputs):
        return {
            "name": name,
            "description": description,
            "tags": ["website", "creator", "read-only"],
            "inputs": inputs,
            "outputs": outputs,
            "tool_call_template": {
                "name": name, "call_template_type": "http",
                "url": origin + ROUTES[name], "http_method": "GET",
                "content_type": "application/json",
                "allowed_communication_protocols": ["http"],
            },
        }

    empty = {"type": "object", "properties": {}, "additionalProperties": False}
    return {
        "utcp_version": VERSION, "manual_version": "1.0.0",
        "tools": [
            tool("list_profiles", "List proposed website development profiles, not installed tools.", empty,
                 {"type": "object", "properties": {"profiles": {"type": "array", "items": {"type": "object"}}}}),
            tool("list_design_options", "List original supported themes, layout presets and defaults.", empty,
                 {"type": "object", "properties": {
                     "themes": {"type": "array", "items": {"type": "string"}},
                     "choices": {"type": "object"}, "defaults": {"type": "object"}}}),
            tool("search_sources", "Search local resource metadata only; returned links require item-level license review.",
                 {"type": "object", "properties": {
                     "query": {"type": "string", "minLength": 1, "maxLength": 160},
                     "import_policy": {"type": "string", "enum": sorted(IMPORT_POLICY)}},
                  "required": ["query"], "additionalProperties": False},
                 {"type": "object", "properties": {"sources": {"type": "array", "items": {"type": "object"}}}}),
        ],
    }


def dispatch(path, query):
    if path == ROUTES["list_design_options"]:
        if query:
            raise ValueError("Unexpected parameters")
        return {"themes": sorted(THEMES), "choices": DESIGN_CHOICES, "defaults": DEFAULT_DESIGN}
    sources, profiles, tools = load_catalog()
    validate(sources, profiles, tools)
    if path == ROUTES["list_profiles"]:
        if query:
            raise ValueError("Unexpected parameters")
        return {"profiles": profiles}
    if path != ROUTES["search_sources"]:
        raise ValueError("Unknown tool")
    if set(query) - {"query", "import_policy"} or any(len(v) != 1 for v in query.values()):
        raise ValueError("Invalid search parameters")
    words = query.get("query", [""])[0]
    policy = query.get("import_policy", [None])[0]
    if not words.strip() or len(words) > 160 or (policy is not None and policy not in IMPORT_POLICY):
        raise ValueError("Invalid search")
    return {"sources": search_sources(sources, words, policy)}


def make_handler(port):
    host = f"127.0.0.1:{port}"

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, *args):
            pass

        def reply(self, code, value):
            data = json.dumps(value).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.headers.get("Host") != host:
                self.reply(403, {"error": "Loopback host required"})
                return
            if len(self.path) > 2048:
                self.reply(400, {"error": "Request too large"})
                return
            try:
                parsed = urlsplit(self.path)
                if parsed.scheme or parsed.netloc or parsed.fragment:
                    raise ValueError("Expected relative route")
                if parsed.path == "/utcp" and not parsed.query:
                    self.reply(200, manual(port))
                elif parsed.path in ROUTES.values():
                    self.reply(200, dispatch(parsed.path, parse_qs(parsed.query, keep_blank_values=True, max_num_fields=2)))
                else:
                    self.reply(404, {"error": "Unknown route"})
            except ValueError:
                self.reply(400, {"error": "Invalid tool parameters"})
            except (OSError, KeyError, TypeError):
                self.reply(500, {"error": "Local catalogue unavailable"})

        def do_POST(self):
            self.reply(405, {"error": "Read-only provider"})

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args()
    manual(args.port)
    with ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.port)) as server:
        print(f"UTCP discovery: http://127.0.0.1:{args.port}/utcp (read-only, local only)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
