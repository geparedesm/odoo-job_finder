"""Exercise action wiring without an Odoo installation."""

import importlib.util
from contextlib import nullcontext
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]


class UserError(Exception):
    pass


class Record(SimpleNamespace):
    def __getitem__(self, name):
        return getattr(self, name)


class Postings(list):
    @property
    def ids(self):
        return [posting.id for posting in self]

    def sorted(self, **kwargs):
        return Postings(sorted(self, **kwargs))


class TestJobActions(unittest.TestCase):
    def setUp(self):
        package = ModuleType("action_test_models")
        package.__path__ = [str(ROOT / "models")]
        odoo = ModuleType("odoo")
        odoo.fields = SimpleNamespace(**{
            name: Mock() for name in ("Integer", "Char", "Text", "Date", "Datetime", "Binary", "Many2one")
        })
        odoo.api = SimpleNamespace(depends=lambda *args: lambda fn: fn,
                                   depends_context=lambda *args: lambda fn: fn)
        odoo.models = SimpleNamespace(Model=object)
        exceptions = ModuleType("odoo.exceptions")
        exceptions.UserError = UserError
        sql_tools = ModuleType("odoo.tools")
        sql_tools.SQL = Mock()
        modules = patch.dict(sys.modules, {
            "action_test_models": package, "odoo": odoo,
            "odoo.exceptions": exceptions, "odoo.tools": sql_tools,
        })
        modules.start()
        self.addCleanup(modules.stop)
        self.models = {}
        for name in ("job_profile", "job_posting"):
            spec = importlib.util.spec_from_file_location(
                f"action_test_models.{name}", ROOT / "models" / f"{name}.py",
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.models[name] = module
        self.actions = Mock()
        self.actions._for_xml_id.return_value = {"res_model": "job.posting"}
        self.catalog = Mock()
        self.profiles = Mock()
        self.env = {
            "ir.actions.act_window": self.actions,
            "job.posting": self.catalog,
            "job.profile": self.profiles,
        }

    def test_search_scores_title_and_description_and_keeps_zero_matches(self):
        self.catalog.search.return_value = Postings([
            Record(id=1, title="Other", description=False),
            Record(id=2, title="Python", description="SQL"),
            Record(id=3, title=False, description="Python"),
            Record(id=4, title="SQL", description=""),
        ])
        env = type("Env", (dict,), {"context": {"lang": "es_ES"}})(self.env)
        profile = Record(summary=False, skills="Python, SQL", experience="", env=env,
                         ensure_one=Mock())
        action = self.models["job_profile"].JobProfile.action_search_related_jobs(profile)
        self.catalog.search.assert_called_once_with([])
        self.assertEqual(action["domain"], [("id", "in", [2, 3, 4, 1])])
        self.assertEqual(action["context"], {"lang": "es_ES", "related_job_ids": [2, 3, 4, 1]})
        profile.ensure_one.assert_called_once()

    def test_search_empty_catalog(self):
        self.catalog.search.return_value = Postings()
        env = type("Env", (dict,), {"context": {}})(self.env)
        action = self.models["job_profile"].JobProfile.action_search_related_jobs(
            Record(summary="", skills="", experience="", env=env, ensure_one=Mock()),
        )
        self.assertEqual(action["domain"], [("id", "in", [])])

    def test_adapt_writes_only_draft_fields_and_reopens_own_profile(self):
        profile = Record(summary="Python developer", skills="SQL, Python", experience=False,
                         write=Mock(), action_open_my_profile=Mock(return_value={"res_id": 7}))
        self.profiles.search.return_value = profile
        env = type("Env", (dict,), {"uid": 42})(self.env)
        posting = Record(env=env, description="Python", ensure_one=Mock())
        action = self.models["job_posting"].JobPosting.action_adapt_cv(posting)
        self.profiles.search.assert_called_once_with([("user_id", "=", 42)], limit=1)
        self.assertEqual(action, {"res_id": 7})
        written = profile.write.call_args.args[0]
        self.assertEqual(set(written), {"adapted_summary", "adapted_skills"})
        self.assertEqual(written["adapted_skills"], "Python\nSQL")
        self.assertEqual(profile.skills, "SQL, Python")
        self.assertIn("Python developer", written["adapted_summary"])
        posting.ensure_one.assert_called_once()

    def test_missing_profile_raises_without_creating(self):
        self.profiles.search.return_value = False
        env = type("Env", (dict,), {"uid": 42})(self.env)
        with self.assertRaisesRegex(UserError, "Cree su perfil profesional"):
            self.models["job_posting"].JobPosting.action_adapt_cv(
                Record(env=env, description="Python", ensure_one=Mock()),
            )
        self.profiles.create.assert_not_called()

    def run_online(self, results, existing=(), race=False):
        class UniqueViolation(Exception):
            pass
        errors = ModuleType("psycopg2.errors")
        errors.UniqueViolation = UniqueViolation
        profile = Record(skills="Python and SQL", headline="", summary="", experience="", location="Berlin")
        job = Record(id=8, source="arbeitnow", external_id="1", title="Python", description="SQL", write=Mock())
        self.catalog.sudo.return_value = self.catalog
        self.catalog.search.side_effect = [Postings(existing), job] if race else [Postings(existing)]
        self.catalog.create.side_effect = UniqueViolation() if race else None
        self.catalog.create.return_value = job
        self.catalog.browse.return_value = Postings([job]) if results else Postings()
        config = Mock()
        env = type("Env", (dict,), {"uid": 42, "context": {}, "cr": SimpleNamespace(savepoint=Mock(side_effect=nullcontext))})(dict(self.env, **{"ir.config_parameter": config}))
        record = Record(env=env, search=Mock(return_value=profile))
        with patch.dict(sys.modules, {"psycopg2": ModuleType("psycopg2"), "psycopg2.errors": errors}), patch.object(self.models["job_profile"], "fetch_jobs", return_value=results) as fetch:
            action = self.models["job_profile"].JobProfile.action_search_online_jobs(record)
        record.search.assert_called_once_with([("user_id", "=", 42)], limit=1)
        fetch.assert_called_once_with(config.sudo.return_value, "python sql", "Berlin")
        return action, job, env

    def test_online_creates_once_for_duplicate_provider_rows(self):
        row = dict(source="arbeitnow", external_id="1", title="Python", description="SQL")
        action, job, env = self.run_online([row, row])
        self.catalog.create.assert_called_once_with(row)
        env.cr.savepoint.assert_called_once()
        self.assertEqual(action["context"]["related_job_ids"], [8])
        self.assertEqual(action["domain"], [("id", "in", [8])])

    def test_online_updates_existing_source_id_pair(self):
        row = dict(source="arbeitnow", external_id="1", title="Updated")
        existing = Record(id=8, source="arbeitnow", external_id="1", write=Mock())
        self.run_online([row], [existing])
        existing.write.assert_called_once_with(row)
        self.catalog.create.assert_not_called()
        self.catalog.search.assert_called_once_with([("source", "in", ["arbeitnow"]), ("external_id", "in", ["1"])])

    def test_online_concurrent_insert_retries_after_savepoint(self):
        row = dict(source="arbeitnow", external_id="1", title="Python")
        action, job, env = self.run_online([row], race=True)
        env.cr.savepoint.assert_called_once()
        job.write.assert_called_once_with(row)
        self.assertEqual(self.catalog.search.call_args.args[0], [("source", "=", "arbeitnow"), ("external_id", "=", "1")])

    def test_posting_online_button_delegates_to_profile(self):
        self.profiles.action_search_online_jobs.return_value = {"domain": []}
        action = self.models["job_posting"].JobPosting.action_search_online_jobs(Record(env=self.env))
        self.assertEqual(action, {"domain": []})
        self.profiles.action_search_online_jobs.assert_called_once_with()

    def test_online_missing_profile_is_friendly(self):
        record = Record(env=SimpleNamespace(uid=42), search=Mock(return_value=False))
        errors = ModuleType("psycopg2.errors")
        errors.UniqueViolation = type("UniqueViolation", (Exception,), {})
        with patch.dict(sys.modules, {"psycopg2": ModuleType("psycopg2"), "psycopg2.errors": errors}):
            with self.assertRaisesRegex(UserError, "Cree su perfil profesional"):
                self.models["job_profile"].JobProfile.action_search_online_jobs(record)

    def test_online_empty_results(self):
        action, job, env = self.run_online([])
        self.assertEqual(action["domain"], [("id", "in", [])])
        self.catalog.create.assert_not_called()
        self.catalog.search.assert_not_called()

    def test_ranking_uses_parameterized_sql_before_pagination(self):
        module = self.models["job_posting"]
        posting = Record(env=SimpleNamespace(context={"related_job_ids": [9, 3]}),
                         _order="id", _table="job_posting")
        module.JobPosting._order_to_sql(posting, "id", Mock())
        self.assertEqual(module.SQL.call_args.args[0], "array_position(%s::int[], %s) %s")
        self.assertEqual(module.SQL.call_args.args[1], [9, 3])
        module.SQL.identifier.assert_called_once_with("job_posting", "id")
