"""Validate module files without importing Odoo or executing module code."""

import ast
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


MODULE_ROOT = Path(__file__).resolve().parent.parent
# The checkout may be named workspace; the deployed Odoo addon is job_finder.
MODULE_NAME = "job_finder"
REFERENCE_ATTRIBUTES = ("id", "ref", "parent", "action", "inherit_id", "groups")


def module_files(pattern):
    """Module files only: not Git metadata or platform folders such as .hermes."""
    for path in sorted(MODULE_ROOT.rglob(pattern)):
        if not any(part.startswith(".") for part in path.relative_to(MODULE_ROOT).parts):
            yield path


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

    def test_connector_python_dependencies(self):
        dependencies = self.load_manifest()["external_dependencies"]["python"]
        for dependency in ("pypdf", "requests"):
            with self.subTest(dependency=dependency):
                self.assertEqual(dependencies.count(dependency), 1)

    def test_posting_and_connector_data_registered_once(self):
        data = self.load_manifest()["data"]
        markers = ("job.posting", "model_job_posting", "adzuna_", "jooble_")
        relevant_files = [
            path.relative_to(MODULE_ROOT).as_posix()
            for pattern in ("*.xml", "*.csv")
            for path in module_files(pattern)
            if any(marker in path.read_text(encoding="utf-8") for marker in markers)
        ]
        self.assertTrue(relevant_files)
        for path in relevant_files:
            with self.subTest(path=path):
                self.assertEqual(data.count(path), 1)

    def test_manifest_security_and_view_load_order(self):
        data = self.load_manifest()["data"]
        security = [index for index, path in enumerate(data) if path.startswith("security/")]
        views = [index for index, path in enumerate(data) if path.startswith("views/")]
        self.assertTrue(security)
        self.assertTrue(views)
        self.assertLess(max(security), min(views))
        menus_index = data.index("views/job_profile_menus.xml")
        for path in ("views/job_profile_views.xml", "views/job_posting_views.xml"):
            with self.subTest(path=path):
                self.assertLess(data.index(path), menus_index)

    def test_xml_files_parse(self):
        for path in module_files("*.xml"):
            with self.subTest(path=str(path.relative_to(MODULE_ROOT))):
                ET.parse(path)

    def test_python_files_parse(self):
        for path in module_files("*.py"):
            with self.subTest(path=str(path.relative_to(MODULE_ROOT))):
                # Bytes let Python honor source encoding declarations.
                ast.parse(path.read_bytes(), filename=str(path))

    def test_module_folder_is_a_valid_module_name(self):
        self.assertTrue(MODULE_ROOT.name.isidentifier(), f"Odoo refuses the module folder name {MODULE_ROOT.name!r}")

    def test_xml_ids_belong_to_this_module_or_a_dependency(self):
        # Odoo refuses data that names another module's ID unless that module is installed.
        allowed = {MODULE_NAME, *self.load_manifest().get("depends", [])}
        for path in module_files("*.xml"):
            for element in ET.parse(path).iter():
                for attribute in REFERENCE_ATTRIBUTES:
                    for value in (element.get(attribute) or "").split(","):
                        prefix = value.strip().split(".", 1)[0] if "." in value else None
                        if prefix is not None:
                            with self.subTest(path=path.name, value=value.strip()):
                                self.assertIn(prefix, allowed)

    def test_env_ref_names_this_module_or_a_dependency(self):
        allowed = {MODULE_NAME, *self.load_manifest().get("depends", [])}
        for path in module_files("*.py"):
            for node in ast.walk(ast.parse(path.read_bytes())):
                if (isinstance(node, ast.Call) and getattr(node.func, "attr", None) in ("ref", "_for_xml_id") and node.args
                        and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)
                        and "." in node.args[0].value):
                    with self.subTest(path=path.name, ref=node.args[0].value):
                        self.assertIn(node.args[0].value.split(".", 1)[0], allowed)


if __name__ == "__main__":
    unittest.main()
