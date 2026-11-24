"""Reference planning must not reproduce source content."""
import json
import unittest

from scripts.creator_reference import reference_plan
from scripts.creator_project import validate_spec


class CreatorReferenceTests(unittest.TestCase):
    def test_independent_project(self):
        source = '<nav>Unique original source name</nav><article><img src="private.jpg"><h2>Other text</h2></article><form><input value="private value"></form><custom-secret></custom-secret>'
        result = reference_plan(source, "My project", "My own objective", True)
        serialized = json.dumps(result)
        for secret in ("Unique original source name", "private.jpg", "Other text", "private value", "custom-secret"):
            self.assertNotIn(secret, serialized)
        self.assertEqual(result["observations"]["standard_element_counts"]["article"], 1)
        validate_spec(result["project"])
        self.assertFalse(any(result["project"]["review"].values()))
        self.assertEqual(result["project"]["pages"][0]["interaction"], "none")

    def test_requires_permission(self):
        with self.assertRaises(ValueError):
            reference_plan("<main></main>", "Name", "Objective", False)

    def test_size_limit(self):
        with self.assertRaises(ValueError):
            reference_plan("x" * 65537, "Name", "Objective", True)


if __name__ == "__main__":
    unittest.main()
