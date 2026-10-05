"""Validate shared catalog security declarations without importing Odoo."""

import ast
import csv
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
PERMISSIONS = ("perm_read", "perm_write", "perm_create", "perm_unlink")


class TestJobPostingSecurity(unittest.TestCase):
    def test_catalog_acl_grants(self):
        with (ROOT / "security/ir.model.access.csv").open(newline="", encoding="utf-8") as source:
            rows = [row for row in csv.DictReader(source)
                    if row["model_id:id"] == "model_job_posting"]
        self.assertEqual(len(rows), 2)
        grants = {row["group_id:id"]: tuple(row[key] for key in PERMISSIONS)
                  for row in rows}
        self.assertEqual(grants, {
            "base.group_user": ("1", "0", "0", "0"),
            "base.group_system": ("1", "1", "1", "1"),
        })

    def test_catalog_rules_are_loaded_and_shared(self):
        manifest = ast.literal_eval((ROOT / "__manifest__.py").read_text(encoding="utf-8"))
        rules = []
        for filename in manifest["data"]:
            if filename.endswith(".xml"):
                rules.extend(record for record in ET.parse(ROOT / filename).iter("record")
                             if record.get("model") == "ir.rule"
                             and record.find("field[@name='model_id']").get("ref") == "model_job_posting")
        self.assertEqual(len(rules), 2)
        for suffix, group, permissions in (
            ("user", "base.group_user", (True, False, False, False)),
            ("system", "base.group_system", (True, True, True, True)),
        ):
            with self.subTest(group=group):
                rule = next(record for record in rules
                            if record.get("id") == f"job_posting_rule_{suffix}")
                fields = {field.get("name"): field for field in rule.findall("field")}
                self.assertEqual(ast.literal_eval(fields["domain_force"].text), [(1, "=", 1)])
                self.assertEqual(fields["groups"].get("eval"), f"[(4, ref('{group}'))]")
                self.assertEqual(tuple(ast.literal_eval(fields[key].get("eval"))
                                       for key in PERMISSIONS), permissions)
