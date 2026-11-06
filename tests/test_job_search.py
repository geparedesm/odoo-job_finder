"""Mocked ingestion, queue contract and profile ownership tests."""

import unittest
from unittest.mock import patch

try:
    from odoo import fields
    from odoo.exceptions import AccessError, ValidationError
    from odoo.tests import HttpCase, TransactionCase, tagged
except ImportError:
    raise unittest.SkipTest("Odoo not available") from None

from .test_offer_scoring import ELIGIBLE, REQUIRED


@tagged("post_install", "-at_install")
class TestJobSearch(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.owner = cls.env["res.users"].create({"name": "Search owner", "login": "search-owner",
                                                "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])]})
        cls.other = cls.env["res.users"].create({"name": "Other owner", "login": "search-other",
                                                "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])]})
        cls.evaluator = cls.env["res.users"].create({"name": "Evaluator", "login": "search-evaluator",
            "group_ids": [(6, 0, [cls.env.ref("job_finder.group_job_finder_evaluator").id])]})
        cls.profile = cls.env["job.profile"].create({"user_id": cls.owner.id, "full_name": "Search Candidate"})
        cls.area = cls.env["job_finder.cv_area"].create({"profile_id": cls.profile.id, "name": "Frontend"})
        cls.search = cls.env["job_finder.job_search"].create({"profile_id": cls.profile.id,
                                                    "cv_area_id": cls.area.id, "keywords": "Frontend"})
        cls.offers = cls.env["job_finder.job_offer"]

    def row(self, key="one", text=""):
        return {"id": key, "title": "Junior Frontend Developer", "description": text,
                "created": fields.Datetime.now().isoformat() + "Z", "location": {"display_name": "Perth"}}

    def test_ingestion_eligibility_and_dedup(self):
        for index, phrase in enumerate(ELIGIBLE + REQUIRED):
            self.search._ingest([self.row(str(index), phrase)])
        self.search._ingest([self.row("0")])
        records = self.offers.search([("profile_id", "=", self.profile.id)])
        self.assertEqual(len(records), len(ELIGIBLE + REQUIRED))
        for offer in records:
            if int(offer.adzuna_id) < len(ELIGIBLE):
                self.assertEqual((offer.state, offer.ai_state), ("new", "pending"))
                self.assertGreater(offer.rule_score, 0)
            else:
                self.assertEqual((offer.state, offer.rule_score), ("discarded", 0))

    def test_threshold_status_and_replay(self):
        self.search._ingest([self.row()])
        offer = self.offers.search([("profile_id", "=", self.profile.id)])
        offer.write({"state": "applied", "notes": "Applied"})
        self.search._ingest([self.row()])
        self.assertEqual(offer.state, "applied")
        self.assertTrue(offer.applied_at)
        self.profile.score_threshold = 100
        self.search._ingest([self.row("low")])
        self.assertEqual(self.offers.search([("adzuna_id", "=", "low")]).state, "discarded")
        with self.assertRaises(ValidationError), self.cr.savepoint():
            offer.write({"state": "discarded"})

    def test_ownership_and_evaluator(self):
        self.search._ingest([self.row()])
        offer = self.offers.search([("profile_id", "=", self.profile.id)])
        self.assertFalse(self.offers.with_user(self.other).search([("id", "=", offer.id)]))
        self.assertEqual(self.offers.with_user(self.owner).search([("id", "=", offer.id)]), offer)
        evaluator = self.offers.with_user(self.evaluator)
        for operation in (lambda: evaluator.search([]), lambda: offer.with_user(self.evaluator).read(),
                          lambda: offer.with_user(self.evaluator).write({"notes": "x"}),
                          lambda: evaluator.create({}), lambda: offer.with_user(self.evaluator).unlink(),
                          lambda: evaluator.action_propose_searches(), lambda: evaluator.action_search_now(),
                          lambda: evaluator.fields_get(), lambda: evaluator.default_get(["title"])):
            with self.assertRaises(AccessError), self.cr.savepoint():
                operation()
        with self.assertRaises(AccessError):
            self.offers.with_user(self.owner).evaluator_pending()
        self.assertTrue(evaluator.evaluator_pending(1))
        for limit in (0, 101, True, "1"):
            with self.assertRaises(ValidationError):
                evaluator.evaluator_pending(limit)
        for invalid_id in (True, "1", -1, 99999999):
            with self.assertRaises(ValidationError):
                evaluator.evaluator_store_result(invalid_id, {})
        result = dict(ai_state="done", ai_score=80, ai_fit="Good", ai_gaps="None", ai_warnings="Snippet only")
        for score in (True, float("nan"), float("inf"), -1, 101, "80"):
            with self.assertRaises(ValidationError):
                evaluator.evaluator_store_result(offer.id, dict(result, ai_score=score))
        for bad in (dict(result, unknown="x"), dict(result, ai_fit="x" * 10001), dict(result, ai_gaps=False)):
            with self.assertRaises(ValidationError):
                evaluator.evaluator_store_result(offer.id, bad)
        self.evaluator.write({"group_ids": [(4, self.env.ref("base.group_user").id)]})
        with self.assertRaises(AccessError):
            evaluator.search([])
        evaluator.evaluator_store_result(offer.id, result)
        with self.assertRaises(ValidationError):
            evaluator.evaluator_store_result(offer.id, result)

    def test_cron_budget_fairness(self):
        area = self.env["job_finder.cv_area"].create({"profile_id": self.profile.id, "name": "Backend"})
        second = self.search.copy({"cv_area_id": area.id, "keywords": "Backend"})
        params = self.env["ir.config_parameter"]
        params.set_param("job_finder.adzuna_app_id", "synthetic")
        params.set_param("job_finder.adzuna_app_key", "synthetic")
        params.set_param("job_finder.adzuna_call_limit", "1")
        from odoo.addons.job_finder.models.adzuna_client import AdzunaClient
        calls = []
        def mocked(client, keywords, city="", page=1):
            client.calls += 1
            calls.append(keywords)
            return []
        with patch.object(AdzunaClient, "search", mocked):
            (self.search | second)._run_searches()
            (self.search | second)._run_searches()
        self.assertEqual(calls, ["Frontend", "Backend"])

    def test_location_rotation_and_page_cap(self):
        from odoo.addons.job_finder.models.adzuna_client import AdzunaClient
        self.search.write({"cities": "Perth,Melbourne", "is_australia": True, "is_remote": True})
        area = self.env["job_finder.cv_area"].create({"profile_id": self.profile.id, "name": "Backend"})
        second = self.search.copy({"cv_area_id": area.id, "keywords": "Backend"})
        searches = self.search | second
        params = self.env["ir.config_parameter"]
        for key, value in (("app_id", "synthetic"), ("app_key", "synthetic"), ("call_limit", "1")):
            params.set_param("job_finder.adzuna_" + key, value)
        calls = []
        def mocked(client, keywords, city="", page=1):
            client.calls += 1
            calls.append((keywords, city, page))
            return []
        with patch.object(AdzunaClient, "search", mocked):
            for _ in range(8):
                searches.invalidate_recordset(["location_cursor", "last_run_at", "last_run_sequence"])
                with self.assertLogs("odoo.addons.job_finder.models.job_search", level="INFO") as logs:
                    searches._run_searches()
                self.assertIn("call budget reached", " ".join(logs.output))
        expected = {(keyword + suffix, city, 1) for keyword in ("Frontend", "Backend")
                    for city, suffix in (("Perth", ""), ("Melbourne", ""), ("", ""), ("", " remote"))}
        self.assertEqual(set(calls), expected)
        params.set_param("job_finder.adzuna_call_limit", "20")
        calls.clear()
        def full_page(client, keywords, city="", page=1):
            client.calls += 1
            calls.append((keywords, city, page))
            return [self.row(str(index)) for index in range(20)]
        with patch.object(AdzunaClient, "search", full_page):
            searches._run_searches()
        self.assertEqual(len(calls), 16)
        self.assertEqual({page for _, _, page in calls}, {1, 2})

    def test_mocked_provider_matrix_and_locations(self):
        import json
        from odoo.addons.job_finder.models.adzuna_client import AdzunaClient
        self.search.write({"cities": "Melbourne", "is_remote": False})
        params = self.env["ir.config_parameter"]
        for key in ("app_id", "app_key"):
            params.set_param("job_finder.adzuna_" + key, "synthetic")
        params.set_param("job_finder.adzuna_call_limit", "20")
        rows = [self.row(str(index), phrase) for index, phrase in enumerate(ELIGIBLE + REQUIRED)]
        for row in rows:
            row["location"] = {"display_name": "Victoria", "area": ["Australia", "Melbourne"]}
        def mocked(client, keywords, city="", page=1):
            client.calls += 1
            return rows if page == 1 else []
        with patch.object(AdzunaClient, "search", mocked):
            self.search._run_searches()
        for offer in self.offers.search([("profile_id", "=", self.profile.id)]):
            if int(offer.adzuna_id) < len(ELIGIBLE):
                self.assertEqual((offer.state, offer.ai_state), ("new", "pending"))
                self.assertEqual(json.loads(offer.score_breakdown)["location"], 10)
            else:
                self.assertEqual((offer.state, offer.rule_score, offer.ai_state), ("discarded", 0, False))
                self.assertTrue(offer.discard_reason)
        self.assertEqual(self.offers.search_count([("profile_id", "=", self.profile.id)]), len(rows))
        row = self.row("outside")
        row["location"] = {"display_name": "Perth"}
        self.search._ingest([row])
        offer = self.offers.search([("adzuna_id", "=", "outside")])
        self.assertEqual(json.loads(offer.score_breakdown)["location"], 0)
        self.search.is_australia = True
        row["id"] = "nationwide"
        self.search._ingest([row])
        self.assertEqual(json.loads(self.offers.search([("adzuna_id", "=", "nationwide")]).score_breakdown)["location"], 10)

    def test_proposals_preserve_edits(self):
        area = self.env["job_finder.cv_area"].create({"profile_id": self.profile.id, "name": "Robotics",
                                                    "headline": "Control Engineer"})
        technology = self.env["job_finder.technology"]._find_or_create(["RobotOS"])
        role = self.env["job_finder.experience"].create({"profile_id": self.profile.id, "role": "Automation Specialist",
                                                      "cv_area_ids": [(6, 0, area.ids)]})
        self.env["job_finder.project"].create({"profile_id": self.profile.id, "name": "Navigation Platform",
                       "cv_area_ids": [(6, 0, area.ids)], "experience_id": role.id,
                       "technology_ids": [(6, 0, technology.ids)]})
        self.search.with_user(self.owner).action_propose_searches()
        proposed = self.search.search([("cv_area_id", "=", area.id)])
        for term in ("robotics", "control", "automation", "navigation", "robotos"):
            self.assertIn(term, proposed.keywords)
        self.assertEqual(len(proposed.keywords.split()), len(set(proposed.keywords.split())))
        proposed.keywords = "edited"
        self.search.with_user(self.owner).action_propose_searches()
        self.assertEqual(proposed.keywords, "edited")

    def test_summary_technology_periods(self):
        technology = self.env["job_finder.technology"]._find_or_create(["Summary Python"])
        for start, end in (("2020-01-01", "2021-01-01"), ("2020-06-01", "2021-01-01"), ("2023-01-01", "2024-01-01")):
            role = self.env["job_finder.experience"].create({"profile_id": self.profile.id, "role": "Developer",
                                                    "date_start": start, "date_end": end})
            self.env["job_finder.project"].create({"profile_id": self.profile.id, "name": "API",
                                     "experience_id": role.id, "technology_ids": [(6, 0, technology.ids)]})
        self.search._ingest([self.row()])
        offer = self.offers.search([("profile_id", "=", self.profile.id)])
        summary = offer._profile_summary()["technologies"][0]
        self.assertAlmostEqual(summary["years"], 2, places=1)
        self.assertFalse(summary["has_unknown_periods"])

    def test_seniority_stored_and_workflow(self):
        for word in ("Senior", "Lead", "Principal", "Head", "Manager", "Architect"):
            row = self.row(word)
            row["title"] = word + " Frontend Developer"
            self.search._ingest([row])
        self.assertTrue(all(offer.rule_score == 0 and offer.state == "discarded" for offer in
                            self.offers.search([("profile_id", "=", self.profile.id)])))
        self.search._ingest([self.row()])
        offer = self.offers.search([("adzuna_id", "=", "one")])
        for state in ("saved", "applied", "interview", "offer", "rejected", "discarded"):
            offer.write({"state": state, "discard_reason": "Reason", "rejection_reason": "Reason"})
            self.assertTrue(offer.status_changed_at)
            self.assertEqual(offer.state, state)
        self.assertTrue(offer.applied_at and offer.interview_at)

    def test_preview_seed_idempotency(self):
        import runpy
        from pathlib import Path
        namespace = runpy.run_path(str(Path(__file__).parents[1] / ".hermes" / "preview-seed.py"), init_globals={"env": self.env})
        before = self.offers.search_count([("adzuna_id", "like", "synthetic-%")])
        namespace["seed"](self.env)
        self.assertEqual(self.offers.search_count([("adzuna_id", "like", "synthetic-%")]), before)
        self.assertGreater(before, 10)

    def test_invalid_relations(self):
        other_profile = self.env["job.profile"].create({"user_id": self.other.id, "full_name": "Other"})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.search.write({"profile_id": other_profile.id})

    def test_missing_credentials(self):
        from odoo.exceptions import UserError
        from odoo.addons.job_finder.models.adzuna_client import AdzunaClient
        self.env["ir.config_parameter"].set_param("job_finder.adzuna_app_id", "")
        with patch.object(AdzunaClient, "search") as provider:
            with self.assertRaises(UserError):
                self.search._run_searches()
            provider.assert_not_called()

    def test_view_structure(self):
        from lxml import etree
        for xml_id in ("view_job_offer_list", "view_job_offer_search", "view_job_offer_form", "view_job_search_form"):
            view = self.env.ref("job_finder." + xml_id)
            root = etree.fromstring(view.arch_db.encode())
            self.assertIsNotNone(root)
        form = self.env.ref("job_finder.view_job_offer_form").arch_db
        self.assertIn("Not evaluated", form)
        self.assertIn('text="Adzuna"', form)
        self.assertIn('name="action_reject"', form)


@tagged("post_install", "-at_install")
class TestJobSearchViews(HttpCase):
    def test_native_offer_views(self):
        from lxml import etree
        owner = self.env["res.users"].create({"name": "Offer View User", "login": "offer-view-user",
                    "group_ids": [(6, 0, [self.env.ref("base.group_user").id])]})
        model = self.env["job_finder.job_offer"].with_user(owner)
        views = [(self.env.ref("job_finder.view_job_offer_" + kind).id, kind) for kind in ("list", "form", "search")]
        result = model.get_views(views)
        form = etree.fromstring(result["views"]["form"]["arch"].encode())
        self.assertEqual(form.xpath("//notebook/page/@string"), ["Overview", "Score breakdown", "AI evaluation", "Notes"])
        self.assertEqual(form.xpath("//field[@name='source_url']/@widget"), ["url"])
        fields_meta = model.fields_get()
        for name in ("ai_score", "ai_fit", "ai_gaps", "ai_warnings", "ai_evaluated_at", "ai_state"):
            self.assertTrue(fields_meta[name]["readonly"])
