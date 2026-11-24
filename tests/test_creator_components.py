"""Component schema, escaping, original output, and legacy compatibility."""
from pathlib import Path
import unittest

from scripts.creator_components import KINDS
from scripts.creator_project import assemble, read_spec, validate_spec

ROOT = Path(__file__).resolve().parents[1]

SAMPLES = {
    "card": "First <script>\nSecond",
    "article": "First <script>\nSecond",
    "callout": "First <script>\nSecond",
    "faq": "First <script>\nSecond",
    "list": "First <script>\nSecond",
    "steps": "First <script>\nSecond",
    "metrics": "Users | 120\nGrowth | <script>",
    "timeline": "Start | First <script>\nFinish | Second",
    "table": "Name | Value\nFirst | <script>",
}


class ComponentTests(unittest.TestCase):
    def setUp(self):
        self.spec = read_spec(ROOT / "projects" / "example.json")
        self.section = self.spec["pages"][0]["sections"][0]

    def test_legacy_compatibility(self):
        old = assemble(self.spec)
        self.section["kind"] = "card"
        self.assertEqual(old, assemble(self.spec))

    def test_all_component_types(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                self.section.update(kind=kind, heading="Original <heading>", body=SAMPLES[kind])
                files = assemble(self.spec)
                self.assertIn("Original &lt;heading&gt;", files["index.html"])
                self.assertIn("&lt;script&gt;", files["index.html"])
                self.assertNotIn("<script>", files["index.html"])
                if kind != "card":
                    self.assertIn("component-" + kind, files["index.html"])
                if kind == "faq":
                    self.assertIn("<summary>", files["index.html"])
                if kind in ("list", "steps", "timeline"):
                    self.assertIn("<li>", files["index.html"])
                if kind == "metrics":
                    self.assertIn("<dl>", files["index.html"])
                    self.assertIn("<dt>Users</dt><dd>120</dd>", files["index.html"])
                if kind == "table":
                    self.assertIn('<th scope="col">Name</th>', files["index.html"])
                    self.assertIn("<td>First</td>", files["index.html"])

    def test_unknown_kind_rejected(self):
        self.section["kind"] = "script"
        with self.assertRaises(ValueError):
            validate_spec(self.spec)

    def test_unknown_fields_rejected(self):
        self.section["html"] = "<script>example</script>"
        with self.assertRaises(ValueError):
            validate_spec(self.spec)

    def test_list_limits(self):
        self.section.update(kind="list", body="\n".join("Item" for _ in range(31)))
        with self.assertRaises(ValueError):
            validate_spec(self.spec)

    def test_structured_component_shapes(self):
        invalid = {
            "metrics": "Missing separator",
            "timeline": "A | B | C",
            "table": "A | B\nOnly one cell",
        }
        for kind, body in invalid.items():
            with self.subTest(kind=kind):
                self.section.update(kind=kind, body=body)
                with self.assertRaises(ValueError):
                    validate_spec(self.spec)


if __name__ == "__main__":
    unittest.main()
