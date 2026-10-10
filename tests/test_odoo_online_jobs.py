"""Online search through the ORM, with HTTP replaced at the requests boundary."""

from datetime import date
import unittest
from unittest.mock import Mock, patch

try:
    from odoo.exceptions import AccessError, UserError
    from odoo.tests import TransactionCase, tagged
except ImportError:
    raise unittest.SkipTest("needs a running Odoo (--test-enable)")

from ..models import job_posting
from ..models.cv_adapter import adapt_profile
from ..models.job_matcher import score_job


@tagged("post_install", "-at_install")
class TestOnlineJobs(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env["res.users"].create({
            "name": "Online Seeker", "login": "online-seeker",
            "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
        })

    def setUp(self):
        super().setUp()
        # Explicit test values override any configured installation credentials.
        config = self.env["ir.config_parameter"].sudo()
        for name, value in {
            "adzuna_app_id": "test-id", "adzuna_app_key": "test-key",
            "adzuna_country": "gb", "jooble_api_key": "test-key",
        }.items():
            config.set_param(name, value)
        self.profile = self.env["job.profile"].with_user(self.user).create({
            "summary": "Python engineer", "skills": "SQL, Python",
            "experience": "Django", "location": "Berlin",
        })
        self.payloads = {
            "adzuna": {"results": [{
                "id": "t15-online", "title": "Python", "description": "Python",
                "company": {"display_name": "Adzuna Co"},
                "location": {"display_name": "Berlin"},
                "redirect_url": "https://example.invalid/adzuna",
                "created": "2026-10-01T12:00:00Z",
            }]},
            "jooble": {"jobs": [{
                "id": "t15-online", "title": "Python SQL", "snippet": "Django",
                "company": "Jooble Co", "location": "Berlin",
                "link": "https://example.invalid/jooble", "updated": "2026-10-01",
            }]},
            "arbeitnow": {"data": [{
                "slug": "t15-online", "title": "Python SQL", "description": "SQL",
                "company_name": "Arbeitnow Co", "location": "Berlin",
                "url": "https://example.invalid/arbeitnow", "created_at": 1790812800,
            }]},
            "remoteok": [{"legal": "Feed metadata"}, {
                "id": "t15-online", "position": "Python SQL", "description": "Django engineer",
                "company": "RemoteOK Co", "location": "Berlin",
                "url": "https://example.invalid/remoteok", "date": "2026-10-01",
            }],
        }
        # Guard the lower HTTP boundary too: unexpected requests must fail locally.
        guard = patch("requests.sessions.Session.request", side_effect=AssertionError("Unexpected HTTP"))
        guard.start()
        self.addCleanup(guard.stop)
        request = patch("requests.request", side_effect=self.http_response)
        self.http = request.start()
        self.addCleanup(request.stop)

    def http_response(self, method, url, **kwargs):
        routes = {
            "https://api.adzuna.com/v1/api/jobs/gb/search/1": ("adzuna", "GET"),
            "https://jooble.org/api/test-key": ("jooble", "POST"),
            "https://www.arbeitnow.com/api/job-board-api": ("arbeitnow", "GET"),
            "https://remoteok.com/api": ("remoteok", "GET"),
        }
        self.assertIn(url, routes)
        source, expected_method = routes[url]
        self.assertEqual(method, expected_method)
        self.assertEqual(kwargs["timeout"], 5)
        response = Mock()
        response.json.return_value = self.payloads[source]
        return response

    def search_online(self):
        return self.profile.with_user(self.user).action_search_online_jobs()

    def results(self, action):
        return self.env["job.posting"].with_user(self.user).with_context(
            action["context"],
        ).search(action["domain"])

    def test_each_provider_maps_http_fields_into_postings(self):
        jobs = self.results(self.search_online())
        self.assertEqual(set(jobs.mapped("source")), set(self.payloads))
        expected = {
            "adzuna": ("Python", "Python", "Adzuna Co"),
            "jooble": ("Python SQL", "Django", "Jooble Co"),
            "arbeitnow": ("Python SQL", "SQL", "Arbeitnow Co"),
            "remoteok": ("Python SQL", "Django engineer", "RemoteOK Co"),
        }
        for job in jobs:
            with self.subTest(source=job.source):
                self.assertEqual((job.title, job.description, job.company), expected[job.source])
                self.assertEqual(job.external_id, "t15-online")
                self.assertEqual(job.location, "Berlin")
                self.assertEqual(job.source_url, "https://example.invalid/" + job.source)
                self.assertEqual(job.url, job.source_url)
                self.assertEqual(job.date_posted, date(2026, 10, 1))
                self.assertEqual(job.posted_date, job.date_posted)
        self.assertEqual(self.http.call_count, 4)
        for call in self.http.call_args_list:
            if "adzuna.com" in call.args[1]:
                self.assertEqual(call.kwargs["params"]["what"], "sql python")
                self.assertEqual(call.kwargs["params"]["where"], "Berlin")
            if "jooble.org" in call.args[1]:
                self.assertEqual(call.kwargs["json"], {"keywords": "sql python", "location": "Berlin"})

    def test_duplicate_feed_rows_and_repeat_search_update_same_records(self):
        row = self.payloads["adzuna"]["results"][0]
        self.payloads["adzuna"]["results"].append(dict(row))
        first = self.results(self.search_online())
        self.assertEqual(len(first), 4)  # Same external ID across providers is valid.
        row["company"]["display_name"] = "Updated Co"
        self.payloads["adzuna"]["results"][1]["company"] = {"display_name": "Updated Co"}
        second = self.results(self.search_online())
        self.assertEqual(set(first.ids), set(second.ids))
        self.assertEqual(second.filtered(lambda job: job.source == "adzuna").company, "Updated Co")
        self.assertEqual(self.env["job.posting"].search_count([("external_id", "=", "t15-online")]), 4)

    def test_missing_credentials_keep_public_feeds_working(self):
        config = self.env["ir.config_parameter"].sudo()
        for name in ("adzuna_app_id", "adzuna_app_key", "jooble_api_key"):
            config.set_param(name, "")
        jobs = self.results(self.search_online())
        self.assertEqual(set(jobs.mapped("source")), {"arbeitnow", "remoteok"})
        self.assertEqual(self.http.call_count, 2)

    def test_online_action_ranks_with_current_profile_before_pagination(self):
        # The posting action is the entry point used by Buscar ofertas online.
        action = self.env["job.posting"].with_user(self.user).action_search_online_jobs()
        self.assertEqual(action["res_model"], "job.posting")
        jobs = self.results(action)
        self.assertEqual(jobs.mapped("source"), ["remoteok", "jooble", "arbeitnow", "adzuna"])
        values = {name: self.profile[name] for name in ("summary", "skills", "experience")}
        self.assertEqual(jobs.mapped("match_score"), [4, 3, 2, 1])
        for job in jobs:
            self.assertEqual(job.match_score, score_job(values, job.title + "\n" + job.description))
        catalog = jobs.env["job.posting"]
        self.assertEqual(catalog.search(action["domain"], limit=1), jobs[:1])
        self.assertEqual(catalog.search(action["domain"], offset=1, limit=1), jobs[1:2])

    def test_adapt_selected_online_posting_calls_adapter_and_saves_draft(self):
        posting = self.results(self.search_online()).filtered(lambda job: job.source == "jooble")
        values = {name: self.profile[name] for name in ("summary", "skills", "experience")}
        expected = adapt_profile(values, posting.description)
        with patch.object(job_posting, "adapt_profile", wraps=adapt_profile) as adapter:
            action = posting.action_adapt_cv()
        adapter.assert_called_once_with(values, posting.description)
        self.assertEqual((action["res_model"], action["res_id"]), ("job.profile", self.profile.id))
        self.assertEqual(self.profile.adapted_summary, expected["summary"])
        self.assertEqual(self.profile.adapted_skills, expected["skills"])
        self.assertTrue(self.profile.adapted_summary)
        self.assertEqual({name: self.profile[name] for name in values}, values)

    def test_online_search_requires_profile_without_http(self):
        self.profile.unlink()
        with self.assertRaisesRegex(UserError, "Cree su perfil profesional"):
            self.env["job.posting"].with_user(self.user).action_search_online_jobs()
        self.http.assert_not_called()

    def test_fetched_catalog_is_shared_but_other_users_cannot_edit_it(self):
        jobs = self.results(self.search_online())
        other = self.env["res.users"].create({
            "name": "Other Online Seeker", "login": "other-online-seeker",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        shared = self.env["job.posting"].with_user(other).search([("id", "in", jobs.ids)])
        self.assertEqual(set(shared.ids), set(jobs.ids))
        self.assertEqual(len(shared.read(["title"])), 4)
        for operation in (
            lambda: shared[:1].write({"title": "Forbidden"}),
            lambda: shared[:1].unlink(),
            lambda: shared.create({"title": "Forbidden"}),
        ):
            with self.assertRaises(AccessError), self.cr.savepoint():
                operation()

    def test_match_score_uses_viewing_users_profile(self):
        jobs = self.results(self.search_online())
        other = self.env["res.users"].create({
            "name": "Django Seeker", "login": "django-online-seeker",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        self.env["job.profile"].with_user(other).create({"skills": "Django"})
        adzuna = jobs.filtered(lambda job: job.source == "adzuna")
        jooble = jobs.filtered(lambda job: job.source == "jooble")
        self.assertEqual(adzuna.match_score, 1)
        self.assertEqual(adzuna.with_user(other).match_score, 0)
        self.assertEqual(jooble.with_user(other).match_score, 1)
