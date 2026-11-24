"""Regression tests for boundary conditions found during repository review."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.creator_project import build, read_spec, validate_spec, verify, spec_bytes, MAX_SPEC
from scripts.creator_studio import export_zip
from scripts.creator_release import release_report
from scripts.creator_reference import reference_plan
from scripts.creator_visual_reference import visual_plan

ROOT = Path(__file__).resolve().parents[1]


class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.spec = read_spec(ROOT / "projects" / "example.json")

    def test_manifest_metadata_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "site"
            build(self.spec, out)
            path = out / "creator-manifest.json"
            original = json.loads(path.read_text(encoding="utf-8"))
            for field, value in (("backend", "unexpected"), ("network_dependencies", ["unexpected"]),
                                 ("version", True), ("limitations", []), ("unexpected", "extra")):
                with self.subTest(field=field):
                    path.write_text(json.dumps({**original, field: value}), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        verify(self.spec, out)

    def test_portable_page_addresses(self):
        for slug in ("con", "aux", "nul", "prn", "com1", "lpt9"):
            with self.subTest(slug=slug):
                self.spec["pages"][1]["slug"] = slug
                with self.assertRaises(ValueError):
                    validate_spec(self.spec)

    def test_direct_spec_size_bound_and_export_round_trip(self):
        base = copy.deepcopy(self.spec["pages"][0])
        self.spec["pages"] = [base]
        for n in range(1, 12):
            page = copy.deepcopy(base)
            page["slug"] = f"page-{n}"
            page["sections"] = [{"heading": "Original", "body": "日" * 4000}]
            self.spec["pages"].append(page)
        self.assertGreater(len(spec_bytes(self.spec)), MAX_SPEC)
        with self.assertRaises(ValueError):
            validate_spec(self.spec)
        self.spec["pages"].pop()
        validate_spec(self.spec)
        with zipfile.ZipFile(io.BytesIO(export_zip(self.spec))) as archive:
            data = archive.read("project.json")
            self.assertLessEqual(len(data), MAX_SPEC)
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "project.json"
                path.write_bytes(data)
                validate_spec(read_spec(path))

    def test_ambiguous_json_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ambiguous.json"
            for source in ('{"version":1,"version":2}', '{"number":NaN}', '{"number":Infinity}'):
                path.write_text(source, encoding="utf-8")
                with self.subTest(source=source), self.assertRaises(ValueError):
                    read_spec(path)

    def test_invalid_text_and_theme(self):
        for value in ("Title\x00", "\ud800"):
            with self.subTest(value=repr(value)):
                self.spec["title"] = value
                with self.assertRaises(ValueError):
                    validate_spec(self.spec)
        self.spec["title"] = "Original"
        self.spec["theme"] = []
        with self.assertRaises(ValueError):
            validate_spec(self.spec)

    def test_reference_starter_review(self):
        drafts = [
            reference_plan("<main><section></section></main>", "Original", "Guide", True)["project"],
            visual_plan({"shape": "landscape", "palette_family": "cool", "density": "low", "lightness": "light"},
                        "Original", "Guide", True)["project"],
        ]
        for draft in drafts:
            report = release_report(draft)
            self.assertTrue(report["warnings"])
            self.assertFalse(report["publication_ready"])
