"""Check discovery and the native read-only HTTP provider."""
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import unittest

from scripts.creator_utcp import manual, make_handler, ROUTES


class UtcpTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
        self.port = self.server.server_port
        self.server.RequestHandlerClass = make_handler(self.port)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def request(self, path, method="GET", headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.request(method, path, headers=headers or {})
            result = connection.getresponse()
            return result.status, json.loads(result.read())
        finally:
            connection.close()

    def test_manual_and_tools(self):
        status, document = self.request("/utcp")
        self.assertEqual(status, 200)
        self.assertEqual(document, manual(self.port))
        self.assertEqual({t["name"] for t in document["tools"]}, set(ROUTES))
        for tool in document["tools"]:
            call = tool["tool_call_template"]
            self.assertEqual(call["http_method"], "GET")
            self.assertEqual(call["allowed_communication_protocols"], ["http"])
            self.assertEqual(call["url"], f"http://127.0.0.1:{self.port}" + ROUTES[tool["name"]])

    def test_profiles_and_design(self):
        self.assertEqual(len(self.request(ROUTES["list_profiles"])[1]["profiles"]), 6)
        self.assertEqual(len(self.request(ROUTES["list_design_options"])[1]["themes"]), 6)

    def test_search_policy(self):
        code, result = self.request(ROUTES["search_sources"] + "?query=templates&import_policy=reference-only")
        self.assertEqual(code, 200)
        self.assertTrue(result["sources"])
        self.assertTrue(all(s["import_policy"] == "reference-only" for s in result["sources"]))

    def test_reject_mutations_and_unknown_routes(self):
        self.assertEqual(self.request("/api/tools/profiles", method="POST")[0], 405)
        self.assertEqual(self.request("/api/session")[0], 404)
        self.assertEqual(self.request("/AGENTS.md")[0], 404)
        self.assertEqual(self.request("/utcp", headers={"Host": "example.org"})[0], 403)

    def test_reject_invalid_arguments(self):
        route = ROUTES["search_sources"]
        for suffix in ("", "?query=", "?query=a&query=b", "?query=a&import_policy=unknown", "?query=a&url=https://example.org"):
            self.assertEqual(self.request(route + suffix)[0], 400)


if __name__ == "__main__":
    unittest.main()
