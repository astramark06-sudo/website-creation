"""Bounded visual reference planning without copied image content."""
import unittest
from scripts.creator_visual_reference import visual_plan
from scripts.creator_project import validate_spec


class VisualReferenceTests(unittest.TestCase):
    def setUp(self):
        self.observations = {"shape": "landscape", "palette_family": "warm",
                             "density": "medium", "lightness": "light"}

    def test_valid_independent_draft(self):
        result = visual_plan(self.observations, "My original site", "A new guide", True)
        validate_spec(result["project"])
        self.assertEqual(result["project"]["theme"], "plum")
        self.assertEqual(result["project"]["design"]["layout"], "showcase")
        self.assertFalse(any(result["project"]["review"].values()))

    def test_permission_required(self):
        with self.assertRaises(ValueError):
            visual_plan(self.observations, "Site", "Guide", False)

    def test_reject_raw_image_and_unknown_fields(self):
        for key in ("image", "pixels", "source_text", "url"):
            with self.assertRaises(ValueError):
                visual_plan({**self.observations, key: "example"}, "Site", "Guide", True)

    def test_invalid_category(self):
        with self.assertRaises(ValueError):
            visual_plan({**self.observations, "density": "arbitrary"}, "Site", "Guide", True)


if __name__ == "__main__":
    unittest.main()
