"""Reference planning must not reproduce source content."""
import json
import unittest

from scripts.creator_reference import reference_plan, reference_batch_plan
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

    def test_multiple_pages_are_generic_and_private(self):
        sources = ['<nav>Private navigation</nav><a href="https://example.invalid/hidden">Secret link</a>',
                   '<article><h1>Private title</h1><img src="hidden.png"></article><script>privateScript()</script>']
        result = reference_batch_plan(sources, "Independent project", "Original objective", True)
        validate_spec(result["project"])
        self.assertEqual(result["observations"]["reference_count"], 2)
        self.assertEqual(result["observations"]["pages"][1]["standard_element_counts"]["article"], 1)
        self.assertEqual([page["slug"] for page in result["project"]["pages"]], ["home", "topic-2"])
        self.assertEqual(result["project"]["pages"][1]["title"], "Topic 2")
        self.assertFalse(any(result["project"]["review"].values()))
        serialized = json.dumps(result)
        for secret in ("Private navigation", "Secret link", "example.invalid", "Private title", "hidden.png", "privateScript"):
            self.assertNotIn(secret, serialized)

    def test_batch_limits(self):
        for sources in ([], ["one"], ["x"] * 6, ["x" * 32769, "x" * 32768], ["ok", 4]):
            with self.assertRaises(ValueError):
                reference_batch_plan(sources, "Name", "Objective", True)
        with self.assertRaises(ValueError):
            reference_batch_plan(["one", "two"], "Name", "Objective", False)
        with self.assertRaises(ValueError):
            reference_batch_plan(["é" * 32768, "x"], "Name", "Objective", True)

    def test_requires_permission(self):
        with self.assertRaises(ValueError):
            reference_plan("<main></main>", "Name", "Objective", False)

    def test_size_limit(self):
        with self.assertRaises(ValueError):
            reference_plan("x" * 65537, "Name", "Objective", True)


if __name__ == "__main__":
    unittest.main()
