"""Component schema, escaping, original output, and legacy compatibility."""
from pathlib import Path
import unittest

from scripts.creator_components import KINDS
from scripts.creator_project import assemble, read_spec, validate_spec

ROOT = Path(__file__).resolve().parents[1]


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
                self.section.update(kind=kind, heading="Original <heading>", body="First <script>\nSecond")
                files = assemble(self.spec)
                self.assertIn("Original &lt;heading&gt;", files["index.html"])
                self.assertIn("First &lt;script&gt;", files["index.html"])
                self.assertNotIn("First <script>", files["index.html"])
                if kind != "card":
                    self.assertIn("component-" + kind, files["index.html"])
                if kind == "faq":
                    self.assertIn("<summary>", files["index.html"])
                if kind in ("list", "steps"):
                    self.assertIn("<li>Second</li>", files["index.html"])

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


if __name__ == "__main__":
    unittest.main()
