"""Exercise profile opening without an Odoo installation."""

import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch


ROOT = Path(__file__).resolve().parents[1]


class UserError(Exception):
    pass


class ValidationError(Exception):
    pass


class TestJobProfileOpen(unittest.TestCase):
    def setUp(self):
        super().setUp()
        package = ModuleType("profile_open_test_models")
        package.__path__ = [str(ROOT / "models")]
        fields = SimpleNamespace(
            Char=Mock(), Text=Mock(), Binary=Mock(), Many2one=Mock(), Boolean=Mock(),
            Image=Mock(), One2many=Mock(), Integer=Mock(),
            Datetime=Mock(),
        )
        odoo = SimpleNamespace(
            fields=fields, api=SimpleNamespace(constrains=lambda *names: lambda method: method, depends=lambda *names: lambda method: method),
            Command=SimpleNamespace(create=Mock(), set=Mock(), clear=Mock()),
            models=SimpleNamespace(Model=object, Constraint=lambda *args: None),
        )
        exceptions = ModuleType("odoo.exceptions")
        exceptions.UserError = UserError
        exceptions.ValidationError = ValidationError
        self.modules = patch.dict(sys.modules, {
            "profile_open_test_models": package, "odoo": odoo,
            "odoo.exceptions": exceptions,
        })
        self.modules.start()
        self.addCleanup(self.modules.stop)
        spec = importlib.util.spec_from_file_location(
            "profile_open_test_models.job_profile", ROOT / "models/job_profile.py",
        )
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.action = {"type": "ir.actions.act_window"}
        self.actions = SimpleNamespace(_for_xml_id=Mock(return_value=self.action))
        env = MagicMock(uid=42)
        env.__getitem__.return_value = self.actions
        self.profile = SimpleNamespace(
            env=env, search=Mock(return_value=False),
            create=Mock(return_value=SimpleNamespace(id=73)),
        )

    def run_action(self):
        action = self.module.JobProfile.action_open_my_profile(self.profile)
        self.profile.search.assert_called_once_with([("user_id", "=", 42)], limit=1)
        self.profile.env.__getitem__.assert_called_once_with("ir.actions.act_window")
        self.actions._for_xml_id.assert_called_once_with("job_finder.action_my_profile")
        self.assertIs(action, self.action)
        self.assertEqual(action["views"], [(False, "form")])
        return action

    def test_creates_missing_profile(self):
        action = self.run_action()
        self.profile.create.assert_called_once_with({"user_id": 42})
        self.assertEqual(action["res_id"], 73)

    def test_reuses_existing_profile(self):
        self.profile.search.return_value = SimpleNamespace(id=91)
        action = self.run_action()
        self.profile.create.assert_not_called()
        self.assertEqual(action["res_id"], 91)


if __name__ == "__main__":
    unittest.main()
