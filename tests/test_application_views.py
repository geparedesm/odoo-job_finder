"""Application navigation, view contracts, translations and browser workflow."""

import ast
import unittest
from unittest.mock import patch

try:
    from odoo.tests import HttpCase, tagged
    from odoo.tests.common import ChromeBrowser
except ImportError:
    raise unittest.SkipTest("needs Odoo (--test-enable)") from None

from lxml import etree


@tagged("post_install", "-at_install")
class TestApplicationViews(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env["res.users"].create({
            "name": "Application UI User", "login": "application-ui-user",
            "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
        })
        cls.applications = cls.env["job_finder.application"].with_user(cls.user)
        cls.env["res.lang"]._activate_lang("es_ES")
        cls.env["ir.module.module"].search([("name", "=", "job_finder")])._update_translations(["es_ES"])

    def _arch(self, kind, lang="en_US"):
        view = self.env.ref("job_finder.view_job_finder_application_" + kind)
        result = self.applications.with_context(lang=lang).get_view(view.id, kind)
        return etree.fromstring(result["arch"].encode())

    def test_menu_action_and_creation(self):
        menu = self.env.ref("job_finder.menu_job_finder_applications").with_user(self.user)
        self.assertIn(menu.id, self.env["ir.ui.menu"].with_user(self.user)._visible_menu_ids())
        self.assertEqual(menu.parent_id, self.env.ref("job_finder.menu_root"))
        self.assertEqual(menu.sequence, 20)
        self.assertEqual(menu.action.id, self.env.ref("job_finder.action_job_finder_application").id)
        action = self.env["ir.actions.actions"].with_user(self.user)._for_xml_id(
            "job_finder.action_job_finder_application")
        self.assertEqual(action["res_model"], "job_finder.application")
        self.assertEqual(action["view_mode"], "list,form")
        self.assertIn("Record your first application", action["help"])
        creation = self.applications.action_open_application_form()
        self.assertEqual(creation["type"], "ir.actions.act_window")
        self.assertEqual(creation["res_model"], "job_finder.application")
        self.assertEqual(creation["view_mode"], "form")
        self.assertEqual(creation["views"], [(False, "form")])
        self.assertEqual(creation["target"], "current")
        self.assertNotIn("res_id", creation)

    def test_list_and_form_structure(self):
        arch = self._arch("list")
        self.assertEqual(arch.get("create"), "0")
        self.assertEqual(arch.xpath("./field/@name"),
                         ["company", "position", "date_applied", "status", "notes"])
        self.assertEqual(arch.xpath("./field[@name='notes']/@optional"), ["show"])
        [button] = arch.xpath("./header/button")
        self.assertEqual(button.get("name"), "action_open_application_form")
        self.assertEqual(button.get("type"), "object")
        self.assertEqual(button.get("display"), "always")
        self.assertEqual(button.get("string"), "Add application")
        self.assertIn("btn-primary", button.get("class"))
        [status] = arch.xpath("./field[@name='status']")
        self.assertEqual(status.get("widget"), "badge")
        for decoration, key in zip(
            ("info", "warning", "primary", "danger", "success"),
            ("sent", "under_review", "interview", "rejected", "offer_received"),
            strict=True,
        ):
            self.assertEqual(status.get("decoration-" + decoration), f"status == '{key}'")
        form = self._arch("form")
        self.assertEqual(form.xpath("./sheet/group/group/field/@name"),
                         ["company", "position", "date_applied", "status"])
        self.assertTrue(form.xpath("./sheet/field[@name='notes']/@placeholder"))

    def test_search_filter_domains(self):
        arch = self._arch("search")
        self.assertEqual(arch.xpath("./field/@name"), ["company", "position"])
        statuses = ("sent", "under_review", "interview", "rejected", "offer_received")
        records = self.applications.create([
            {"company": "Filter company", "position": key, "status": key} for key in statuses
        ])
        for key in statuses:
            [node] = arch.xpath(f"./filter[@name='filter_{key}']")
            domain = ast.literal_eval(node.get("domain"))
            self.assertEqual(domain, [("status", "=", key)])
            found = self.applications.search([("id", "in", records.ids)] + domain)
            self.assertEqual(found, records.filtered(lambda record, key=key: record.status == key))
        [group] = arch.xpath("./filter[@name='group_by_status']")
        self.assertEqual(ast.literal_eval(group.get("context")), {"group_by": "status"})

    def test_spanish_translations(self):
        menu = self.env.ref("job_finder.menu_job_finder_applications").with_user(self.user)
        self.assertEqual(menu.with_context(lang="es_ES").name, "Mis postulaciones")
        self.assertEqual(self._arch("list", "es_ES").xpath("./header/button/@string"),
                         ["Agregar postulación"])
        labels = self.applications.with_context(lang="es_ES").fields_get(["status"])["status"]["selection"]
        self.assertEqual([label for _key, label in labels],
                         ["Enviada", "En revisión", "Entrevista", "Rechazada", "Oferta recibida"])

    def test_application_tour(self):
        action = self.env.ref("job_finder.action_job_finder_application")
        wait_code_ok = ChromeBrowser._wait_code_ok

        def capture_completed_tour(browser, *args, **kwargs):
            result = wait_code_ok(browser, *args, **kwargs)
            browser.take_screenshot("application_list_").result(timeout=10)
            return result

        with patch.object(ChromeBrowser, "_wait_code_ok", capture_completed_tour):
            self.start_tour(f"/odoo/action-{action.id}", "job_finder_application_tour",
                            login=self.user.login, timeout=180)
        application = self.applications.search([("company", "=", "Tour company")])
        self.assertEqual(len(application), 1)
        self.assertEqual(application.position, "Tour developer")
        self.assertFalse(application.notes)
        self.assertEqual(application.status, "sent")
