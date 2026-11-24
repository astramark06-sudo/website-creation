"""Exercise the actual optional UTCP SDK against the native local provider."""
import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import unittest

from utcp.utcp_client import UtcpClient

from scripts.creator_utcp import make_handler

ROOT = Path(__file__).resolve().parents[2]


class RealUtcpClientTests(unittest.TestCase):
    def test_discover_and_call_native_tools(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
        server.RequestHandlerClass = make_handler(server.server_port)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        async def exercise():
            config = json.loads((ROOT / "integrations" / "utcp" / "local-client.json").read_text(encoding="utf-8"))
            config["manual_call_templates"][0]["url"] = f"http://127.0.0.1:{server.server_port}/utcp"
            client = await UtcpClient.create(config=config)
            try:
                profiles = await client.call_tool("master_creator.list_profiles", {})
                design = await client.call_tool("master_creator.list_design_options", {})
                sources = await client.call_tool("master_creator.search_sources", {
                    "query": "templates", "import_policy": "reference-only"})
                def as_object(value):
                    return json.loads(value) if isinstance(value, str) else value
                self.assertEqual(len(as_object(profiles)["profiles"]), 6)
                self.assertEqual(len(as_object(design)["themes"]), 6)
                matches = as_object(sources)["sources"]
                self.assertTrue(matches)
                self.assertTrue(all(s["import_policy"] == "reference-only" for s in matches))
            finally:
                await client.deregister_manual("master_creator")

        try:
            asyncio.run(asyncio.wait_for(exercise(), timeout=45))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
