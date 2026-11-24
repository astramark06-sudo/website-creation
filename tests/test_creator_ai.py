"""Test the local AI boundary with a fake transport, never real inference."""
import json
import unittest

from scripts.creator_ai import generate_draft, installed_model


class CreatorAITests(unittest.TestCase):
    def example(self):
        return {"title": "Original site", "description": "A new website", "theme": "teal",
                "pages": [{"slug": "home", "title": "Home", "intro": "Welcome",
                           "sections": [{"heading": "About", "body": "Original description"}],
                           "interaction": "none"}]}

    def transport(self, draft, calls):
        def request(path, data=None):
            calls.append((path, data))
            if path == "/api/tags":
                return {"models": [{"name": "local:latest", "size": 100, "digest": "example"}]}
            return {"done": True, "response": json.dumps(draft)}
        return request

    def test_valid_draft(self):
        calls = []
        draft = generate_draft("Make an original site", "local:latest", self.transport(self.example(), calls))
        self.assertFalse(any(draft["review"].values()))
        self.assertEqual(draft["version"], 1)
        self.assertEqual([p for p, _ in calls], ["/api/tags", "/api/generate"])
        self.assertFalse(calls[1][1]["stream"])

    def test_model_cannot_approve_publication(self):
        draft = self.example()
        draft["review"] = {"publish_approved": True}
        with self.assertRaises(ValueError):
            generate_draft("Website", "local:latest", self.transport(draft, []))

    def test_invalid_page_rejected(self):
        draft = self.example()
        draft["pages"][0]["slug"] = "../private"
        with self.assertRaises(ValueError):
            generate_draft("Website", "local:latest", self.transport(draft, []))

    def test_cloud_model_rejected_without_request(self):
        calls = []
        with self.assertRaises(ValueError):
            installed_model("model:cloud", self.transport(self.example(), calls))
        self.assertEqual(calls, [])

    def test_missing_model_never_downloaded(self):
        calls = []
        with self.assertRaises(ValueError):
            generate_draft("Website", "missing", self.transport(self.example(), calls))
        self.assertEqual([p for p, _ in calls], ["/api/tags"])


if __name__ == "__main__":
    unittest.main()
