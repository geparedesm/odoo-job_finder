"""Exercise CV import behavior without an Odoo installation."""

import base64
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]


class UserError(Exception):
    pass


class TestJobProfile(unittest.TestCase):
    def setUp(self):
        package = ModuleType("profile_test_models")
        package.__path__ = [str(ROOT / "models")]
        fields = SimpleNamespace(
            Char=Mock(), Text=Mock(), Binary=Mock(), Many2one=Mock(),
            Datetime=Mock(now=Mock(return_value="2026-10-02 12:00:00")),
        )
        odoo = ModuleType("odoo")
        odoo.fields = fields
        odoo.models = SimpleNamespace(Model=object)
        exceptions = ModuleType("odoo.exceptions")
        exceptions.UserError = UserError
        self.modules = patch.dict(sys.modules, {
            "profile_test_models": package, "odoo": odoo,
            "odoo.exceptions": exceptions,
        })
        self.modules.start()
        self.addCleanup(self.modules.stop)
        spec = importlib.util.spec_from_file_location(
            "profile_test_models.job_profile", ROOT / "models/job_profile.py",
        )
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.profile = SimpleNamespace(
            cv_file=base64.b64encode(b"PDF bytes"), write=Mock(),
        )
        self.reader = Mock(return_value=SimpleNamespace(pages=[]))
        self.pdf = patch.dict(sys.modules, {
            "pypdf": SimpleNamespace(PdfReader=self.reader),
        })
        self.pdf.start()
        self.addCleanup(self.pdf.stop)

    def run_action(self, profiles=None):
        self.module.JobProfile.action_parse_cv(
            profiles if profiles is not None else [self.profile],
        )

    def test_all_pages_and_whitelisted_fields(self):
        self.reader.return_value.pages = [
            Mock(extract_text=Mock(return_value="First")),
            Mock(extract_text=Mock(return_value="Second")),
        ]
        with patch.object(self.module, "parse_cv_text", return_value={
            "full_name": "Ana", "skills": "Python", "email": "",
            "extra_info": "Must never overwrite", "user_id": 42,
        }) as parser:
            self.run_action()
        parser.assert_called_once_with("First\nSecond")
        self.assertEqual(self.reader.call_args.args[0].getvalue(), b"PDF bytes")
        self.profile.write.assert_called_once_with({
            "full_name": "Ana", "skills": "Python",
            "cv_raw_text": "First\nSecond",
            "cv_parsed_date": "2026-10-02 12:00:00",
        })

    def test_unreadable_pdf_and_empty_fields(self):
        self.reader.side_effect = ValueError("Invalid PDF")
        self.run_action()
        self.profile.write.assert_called_once_with({
            "cv_raw_text": "", "cv_parsed_date": "2026-10-02 12:00:00",
        })

    def test_failed_page_does_not_discard_readable_pages(self):
        self.reader.return_value.pages = [
            Mock(extract_text=Mock(side_effect=ValueError("Bad page"))),
            Mock(extract_text=Mock(return_value=None)),
            Mock(extract_text=Mock(return_value="Ana\nSKILLS\nPython")),
        ]
        self.run_action()
        values = self.profile.write.call_args.args[0]
        self.assertEqual(values["skills"], "Python")
        self.assertNotIn("extra_info", values)

    def test_missing_library_has_spanish_error(self):
        with patch.dict(sys.modules, {"pypdf": None}):
            with self.assertRaisesRegex(UserError, "Instale la librería pypdf"):
                self.run_action()
        self.profile.write.assert_not_called()

    def test_recordset_and_missing_upload(self):
        empty = SimpleNamespace(cv_file=False, write=Mock())
        other = SimpleNamespace(cv_file=self.profile.cv_file, write=Mock())
        self.run_action([self.profile, empty, other])
        self.profile.write.assert_called_once()
        other.write.assert_called_once()
        empty.write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
