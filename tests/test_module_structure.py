"""Validate module files without importing Odoo or executing module code."""

import ast
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


MODULE_ROOT = Path(__file__).resolve().parent.parent


class TestModuleStructure(unittest.TestCase):
    def load_manifest(self):
        manifest = ast.literal_eval(
            (MODULE_ROOT / "__manifest__.py").read_text(encoding="utf-8")
        )
        self.assertIsInstance(manifest, dict)
        return manifest

    def test_manifest_structure(self):
        manifest = self.load_manifest()
        self.assertIsInstance(manifest.get("name"), str)
        self.assertTrue(manifest["name"].strip())
        for key in ("depends", "data", "demo"):
            if key in manifest:
                with self.subTest(key=key):
                    self.assertIsInstance(manifest[key], list)
                    for value in manifest[key]:
                        self.assertIsInstance(value, str)

    def test_manifest_files_exist(self):
        manifest = self.load_manifest()
        for key in ("data", "demo"):
            paths = manifest.get(key, [])
            self.assertIsInstance(paths, list)
            for path in paths:
                with self.subTest(key=key, path=path):
                    self.assertIsInstance(path, str)
                    self.assertTrue((MODULE_ROOT / path).is_file())

    def test_xml_files_parse(self):
        for path in sorted(MODULE_ROOT.rglob("*.xml")):
            with self.subTest(path=str(path.relative_to(MODULE_ROOT))):
                ET.parse(path)

    def test_python_files_parse(self):
        for path in sorted(MODULE_ROOT.rglob("*.py")):
            with self.subTest(path=str(path.relative_to(MODULE_ROOT))):
                # Bytes let Python honor source encoding declarations.
                ast.parse(path.read_bytes(), filename=str(path))


if __name__ == "__main__":
    unittest.main()
