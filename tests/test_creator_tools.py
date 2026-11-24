"""Shared native discovery and studio planning boundaries."""
import unittest

from scripts.creator_tools import overview, query_tool, propose_plan


class CreatorToolsTests(unittest.TestCase):
    def test_overview(self):
        result = overview(8765)
        self.assertEqual(result["counts"]["registered_tools"], 90)
        self.assertEqual(result["counts"]["sources"], 31)
        self.assertEqual(len(result["native_tools"]), 3)

    def test_source_query(self):
        result = query_tool({"tool": "search_sources", "arguments": {
            "query": "templates", "import_policy": "reference-only"}})
        self.assertTrue(result["sources"])
        self.assertTrue(all(s["import_policy"] == "reference-only" for s in result["sources"]))

    def test_proposal_does_not_install(self):
        result = propose_plan({"profile": "marketing", "objective": "An original studio"})
        self.assertEqual(result["state"], "proposal-only")
        self.assertEqual(result["network_calls"], 0)
        self.assertFalse(result["paid_services"])

    def test_reject_arbitrary_tool_and_parameters(self):
        for payload in (
            {"tool": "shell", "arguments": {}},
            {"tool": "search_sources", "arguments": {"query": "templates", "url": "https://example.org"}},
            {"tool": "list_profiles", "arguments": {"extra": 1}},
        ):
            with self.assertRaises(ValueError):
                query_tool(payload)


if __name__ == "__main__":
    unittest.main()
