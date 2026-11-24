"""Offline planning and source-policy regression tests."""
import copy
import unittest

from scripts.creator_plan import load_catalog, plan, validate


class CreatorPlanTests(unittest.TestCase):
    def setUp(self):
        self.sources, self.profiles, self.tools = load_catalog()

    def test_catalog_valid(self):
        validate(self.sources, self.profiles, self.tools)
        self.assertGreaterEqual(len(self.sources), 18)
        self.assertEqual(len(self.profiles), 6)

    def test_plan_is_proposal_only(self):
        result = plan("interactive", "A task dashboard", self.sources, self.profiles, self.tools)
        self.assertEqual(result["framework_candidate"], "vite")
        self.assertEqual(result["state"], "proposal-only")
        self.assertEqual(result["network_calls"], 0)
        self.assertFalse(result["paid_services"])

    def test_requires_objective(self):
        with self.assertRaises(ValueError):
            plan("marketing", " ", self.sources, self.profiles, self.tools)

    def test_unknown_tool_rejected(self):
        profiles = copy.deepcopy(self.profiles)
        profiles[0]["required"].append("unknown")
        with self.assertRaises(ValueError):
            validate(self.sources, profiles, self.tools)

    def test_duplicate_source_rejected(self):
        with self.assertRaises(ValueError):
            validate(self.sources + self.sources[:1], self.profiles, self.tools)

    def test_unreviewed_adoption_rejected(self):
        sources = copy.deepcopy(self.sources)
        sources[0]["adoption"] = "auto-install"
        with self.assertRaises(ValueError):
            validate(sources, self.profiles, self.tools)


if __name__ == "__main__":
    unittest.main()
