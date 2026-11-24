"""Test bounded local vision transport using synthetic marker data, not inference."""
import base64
import json
import unittest

from scripts.creator_vision import checked_image, vision_plan


def marker_image(width=16, height=16):
    # A frame-header fixture for the boundary parser, not a decodable photo.
    frame = b"\xff\xd8\xff\xc0\x00\x0b\x08" + height.to_bytes(2, "big") + width.to_bytes(2, "big") + b"\x01\x01\x11\x00\xff\xd9"
    return base64.b64encode(frame).decode("ascii")


class VisionTests(unittest.TestCase):
    def setUp(self):
        self.selection = {"theme": "forest", "design": {"layout": "editorial", "typeface": "editorial",
                           "density": "spacious", "surface": "flat"}, "structure": "editorial"}
        self.calls = []

    def transport(self, path, data=None):
        self.calls.append((path, data))
        if path == "/api/tags":
            return {"models": [{"name": "vision:local", "size": 100, "digest": "example"}]}
        return {"done": True, "response": json.dumps(self.selection)}

    def test_valid_selection(self):
        result = vision_plan(marker_image(), "Original", "Independent guide", True, "vision:local", self.transport)
        self.assertEqual(result["project"]["theme"], "forest")
        self.assertFalse(any(result["project"]["review"].values()))
        self.assertEqual([p for p, _ in self.calls], ["/api/tags", "/api/generate"])
        self.assertEqual(self.calls[-1][1]["images"], [marker_image()])
        self.assertTrue(all(section["body"] == "Add original content." for section in result["project"]["pages"][0]["sections"]))

    def test_consent_and_invalid_input_before_transport(self):
        for image, authorized in [(marker_image(), False), ("not base64", True), (marker_image(769), True)]:
            with self.subTest(authorized=authorized), self.assertRaises(ValueError):
                vision_plan(image, "Original", "Guide", authorized, "vision:local", self.transport)
        self.assertEqual(self.calls, [])

    def test_strict_json_response(self):
        for raw in ('{"theme":"forest","theme":"blue"}', '{"theme":NaN}', "[" * 2000 + "]" * 2000):
            def transport(path, data=None):
                if path == "/api/tags":
                    return {"models": [{"name": "vision:local", "size": 100, "digest": "example"}]}
                return {"done": True, "response": raw}
            with self.subTest(length=len(raw)), self.assertRaises(ValueError):
                vision_plan(marker_image(), "Original", "Guide", True, "vision:local", transport)

    def test_extra_model_output_is_rejected(self):
        self.selection["html"] = "<script>bad</script>"
        with self.assertRaises(ValueError):
            vision_plan(marker_image(), "Original", "Guide", True, "vision:local", self.transport)

    def test_unsupported_selection(self):
        self.selection["design"]["layout"] = "arbitrary"
        with self.assertRaises(ValueError):
            vision_plan(marker_image(), "Original", "Guide", True, "vision:local", self.transport)

    def test_cloud_model_rejected(self):
        with self.assertRaises(ValueError):
            vision_plan(marker_image(), "Original", "Guide", True, "vision:cloud", self.transport)
        self.assertEqual(self.calls, [])
