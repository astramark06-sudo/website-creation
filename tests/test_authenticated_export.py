"""Verify deterministic, allowlisted authenticated staging bundles without Django."""
import hashlib
import io
import json
from pathlib import Path
import unittest
import zipfile

from scripts.creator_authenticated_export import export_authenticated, SOURCE_FILES
from scripts.creator_relational import read_schema

ROOT = Path(__file__).resolve().parents[1]


class AuthenticatedExportTests(unittest.TestCase):
    def test_deterministic_bundle_and_manifest(self):
        schema = read_schema(ROOT / "projects" / "relational-example.json")
        bundle = export_authenticated("Example", "Original staging", schema)
        self.assertEqual(bundle, export_authenticated("Example", "Original staging", schema))
        with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
            self.assertEqual(set(archive.namelist()), set(SOURCE_FILES) | {
                "scripts/__init__.py", "workspace-config.json", ".gitignore", "README.md", "bundle-manifest.json",
            })
            manifest = json.loads(archive.read("bundle-manifest.json"))
            self.assertFalse(manifest["public_deployment"])
            self.assertEqual(set(manifest["files"]), set(archive.namelist()) - {"bundle-manifest.json"})
            for name, digest in manifest["files"].items():
                self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), digest)
                if name.endswith(".py"):
                    compile(archive.read(name), name, "exec")
            self.assertEqual(json.loads(archive.read("workspace-config.json"))["schema"], schema)

    def test_invalid_schema_rejected(self):
        with self.assertRaises(ValueError):
            export_authenticated("Example", "Original staging", {"version": 1, "tables": []})
